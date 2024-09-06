#!/usr/bin/env python3

import sys
from collections import OrderedDict
import json
import os
import copy
import logging
import urllib.request
from enum import Enum

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s %(levelname)s:%(message)s')

# Github Download setup and credentials
SARSCOV2_ALIAS_KEY_URL     = "https://api.github.com/repos/cov-lineages/pango-designation/contents/pango_designation/alias_key.json"
SARSCOV2_LINEAGE_NOTES_URL = "https://api.github.com/repos/cov-lineages/pango-designation/contents/lineage_notes.txt"

# -----------------------------------------------------------------------------
# Organisms

class Organism(Enum):
    SARSCOV2 = "sars-cov-2"
    MPOX = "mpox"

    @staticmethod
    def from_str(name):
        """
        Source: https://stackoverflow.com/a/49060635
        Author: rogueleaderr
        """
        if name == "sars-cov-2":
            return Organism.SARSCOV2
        elif name == "mpox":
            return Organism.MPOX
        elif not name:
            raise Exception(f"An organism name must be provided.")
        else:
            raise NotImplementedError(f"The organism '{name}' is not implemented yet.")

    @property
    def alias_key_url(self):
        if self == Organism.SARSCOV2:
            return "https://api.github.com/repos/cov-lineages/pango-designation/contents/pango_designation/alias_key.json"
        elif self == Organism.MPOX:
            return "https://api.github.com/repos/mpxv-lineages/lineage-designation/contents/auto-generated/alias_key.json"
        
    @property
    def lineage_notes_url(self):
        if self == Organism.SARSCOV2:
            return "https://api.github.com/repos/cov-lineages/pango-designation/contents/lineage_notes.txt"
        elif self == Organism.MPOX:
            return "https://api.github.com/repos/mpxv-lineages/lineage-designation/contents/auto-generated/lineages.md"
            #return "https://api.github.com/repos/mpxv-lineages/lineage-designation/contents/auto-generated/lineages.json"

class Direction(Enum):
    ToRoot = 0
    ToTips = 1
    Unknown = 2

class PangoNet:

    def __init__(self):

        self.aliases = dict()
        self.hierarchy = OrderedDict()
        self.network = OrderedDict()
        self.organism = None
        self.root = None      
        self.lineages = list()

    def bfs(self, network: OrderedDict = None, start: str = None):
        """Perform a breadth-first search, returning all lineages encountered."""

        if not network:
            network = self.network

        if not start:
            start = self.root

        nodes = [start]
        # Get all nodes that are 1 deeper but also descendants of the start
        descendants = self.get_descendants(lineage=start, network=network)
        curr_depth = network[start]["depth"]
        next_nodes = ["fake_value"]
        while len(next_nodes) > 0:
            curr_depth += 1
            next_nodes = [d for d in descendants if network[d]["depth"] == curr_depth]
            nodes += next_nodes
        return nodes

    def build(self, organism: str = None, root: str = "root", alias_key: str = None, lineage_notes: str = None, outdir: str = "."):
        '''
        root: If not None, manually create top level node with this name
        '''

        self.root = root
        self.organism = Organism.from_str(organism)

        if outdir != "" and outdir != "." and not os.path.exists(outdir):
            os.makedirs(outdir)
        # Download alias key if not provided
        if not alias_key:
            alias_key_url = self.organism.alias_key_url
            alias_key_path = os.path.join(outdir, os.path.basename(alias_key_url))
            self.download_file(url = alias_key_url, output = alias_key_path)
        else:
            alias_key_path = alias_key
        
        # Download lineage notes if not provided
        if not lineage_notes:
            lineage_notes_url = self.organism.lineage_notes_url
            lineage_notes_path = os.path.join(outdir, os.path.basename(lineage_notes_url))
            self.download_file(url = lineage_notes_url, output = lineage_notes_path)
        else:
            lineage_notes_path = lineage_notes

        self.aliases      = self.parse_aliases(alias_key_path)    
        self.recombinants = self.parse_recombinants(alias_key_path)

        if self.organism == Organism.SARSCOV2:
            self.lineages     = self.parse_sarscov2_lineages(lineage_notes_path)
        elif self.organism == Organism.MPOX:
            self.lineages     = self.parse_mpox_lineages(lineage_notes_path)
    
        self.network = self.create_network()

        return self

    def compress(self, lineage):
        '''
        Compress lineage name
        '''
        compressed = lineage
        try:
            uncompressed = self.uncompress(lineage)
        except Exception as e:
            uncompressed = lineage

        lineage_split = uncompressed.split(".")
        # Simple compression, since the lineage is already decompressed
        match_found = False
        for i in range(1,len(lineage_split)):
            prefix = ".".join(lineage_split[0:len(lineage_split)-i])
            suffix = ".".join(lineage_split[len(lineage_split)-i:])
            for a,info in self.aliases.items():
                if info["uncompressed"] == prefix:
                    compressed = ".".join([a, suffix])
                    match_found = True
                    break
            if match_found: break

        # If the alias does not exist in the network, raise an error
        if compressed not in self.lineages:
            raise Exception(f"Alias {compressed} of lineage {lineage} does not exist.")

        return(compressed)

    def create_network(self):
        '''
        root : If not None, manually create top level node with this name
        '''
        logging.info(f"Creating network.")

        network = OrderedDict()
        # Manually add a root node according to params
        if self.root:
            network[self.root] = {"uncompressed": "", "depth": 0, "parents": [], "children": [], "ancestors": [], "descendants": [], "alias": None}
        root = self.root

        # ---------------------------------------------------------------------
        # Iteration #1: Parents

        for lineage in self.lineages:

            uncompressed = self.uncompress(lineage)
            uncompressed_split = uncompressed.split(".")

            alias = None
            for a,info in self.aliases.items():
                if info["uncompressed"] == uncompressed:
                    alias = a
                    break            

            # Option 1: Root node
            # If we don't have a root yet, assign to first one encountered
            # This functionality isn't used for SARS-CoV-2
            if not root:
                root = lineage
                depth = 0
                parents = []
            # Option 2: Lookup recombinant parents
            elif lineage in self.recombinants:
                parents = self.recombinants[lineage]
            else:
                # Option 3: Top level node, A or B
                if "." not in uncompressed:
                    parents = [self.root]
                elif self.organism == Organism.SARSCOV2:
                    uncompressed_parent = uncompressed_split[0: (len(uncompressed_split) - 1)]
                    parents = [self.compress(".".join(uncompressed_parent))]
                elif self.organism == Organism.MPOX:
                    parents = [self.hierarchy[lineage]]

            network[lineage] = {"uncompressed": uncompressed, "depth": 0, "parents": parents, "children": [], "ancestors": [], "descendants": [], "alias": alias }

        # ---------------------------------------------------------------------
        # Iteratation #2: Children

        for lineage,info in network.items():
            for parent in info["parents"]:
               network[parent]["children"].append(lineage)

        # ---------------------------------------------------------------------
        # Iteratation #3: Descendants and Ancestors
    
        for lineage in network:
           network[lineage]["ancestors"] = self.get_ancestors(lineage=lineage, network=network)
           network[lineage]["descendants"] = self.get_descendants(lineage=lineage, network=network)

        # ---------------------------------------------------------------------
        # Iteratation #5: uncompressed aliases

        lineages = list(network.keys())
        # Maybe only for sars-cov-2, because we need to rethink how compress/uncompress works for mpox
        if self.organism == Organism.SARSCOV2:        
            for lineage in lineages:
                uncompressed = network[lineage]["uncompressed"]
                if uncompressed and uncompressed != '' and uncompressed not in network:
                    network[uncompressed] = network[lineage]

        # ---------------------------------------------------------------------
        # Iteratation #4: Depth

        recombinants = self.get_recombinants(network=network, descendants=True)

        for lineage,info in network.items():
            if lineage == self.root:
                depth = 0
            elif lineage in recombinants:
                max_parent_depth = 0
                for parent in network[lineage]["parents"]:
                    parent_depth = network[parent]["depth"]                 
                    if parent_depth > max_parent_depth:
                        max_parent_depth = parent_depth
                depth = max_parent_depth + 1
            else:
                depth = len(info["uncompressed"].split("."))
            network[lineage]["depth"] = depth
            
        # ---------------------------------------------------------------------
        # Order network nodes by a depth-first search (DFS)

        lineage_order = self.dfs(network=network, start="root")
        network = {lineage:network[lineage] for lineage in lineage_order}
        
        return network

    
    def dfs(self, network: OrderedDict = None, start: str = None, nodes = None):
        """Perform a depth first search, returning all lineages encountered."""

        if not network:
            network = self.network

        if not nodes:
            nodes = []

        if not start:
            start = self.root

        nodes.append(start)
        for child in self.get_children(lineage=start, network=network):
            self.dfs(start=child, nodes=nodes, network=network)
        return nodes 

    def download_file(self, url: str, output: str = None):

        logging.info(f"Downloading file: {output}")

        req = urllib.request.Request(url)
        # Try to add a github token if needed
        if "github" in url:
            github_token = os.environ.get('GITHUB_TOKEN')
            if github_token:
                req.add_header('Authorization', f"Bearer {github_token}")
            # If URL is actually a github api call
            if "api.github.com" in url:
                response = urllib.request.urlopen(req)
                url = json.loads(response.read())["download_url"]
                req = urllib.request.Request(url)

        # Download file
        with open(output, 'w', encoding="utf-8") as outfile:
            response = urllib.request.urlopen(req)
            content = response.read().decode("utf-8", 'ignore')
            outfile.write(content)

        return output

    def filter(self, lineages: [str], network: OrderedDict = None):
        '''
        Filter network to only the specified lineages.
        '''

        if not network:
            network = self.network
        
        # Keep order of lineages in network
        lineages = [l for l in network if l in lineages]
        pango = copy.deepcopy(self)    

        filtered_network = OrderedDict()        
        for lineage in lineages:
            info = network[lineage]
            filtered_network[lineage] = copy.deepcopy(network[lineage])
            filtered_network[lineage]["parents"]     = [l for l in info["parents"]     if l in lineages]
            filtered_network[lineage]["children"]    = [l for l in info["children"]    if l in lineages]
            filtered_network[lineage]["ancestors"]   = [l for l in info["ancestors"]   if l in lineages]
            filtered_network[lineage]["descendants"] = [l for l in info["descendants"] if l in lineages]

        pango.network = filtered_network
        # Update attributes
        pango.recombinants = self.get_recombinants()
        return pango


    def get_ancestors(self, lineage: str, network : OrderedDict = None):
        '''
        Get all ancestors between lineage and the root node.
        '''

        if not network:
            network = self.network

        ancestors = []

        parents = network[lineage]["parents"]
        if len(parents) == 0:
            return []
        for parent in network[lineage]["parents"]:
            parent_ancestors = self.get_ancestors(lineage=parent, network=network)
            ancestors += [parent] + parent_ancestors
        # remove duplicates (python 3.7+ preserves order)
        ancestors = list(dict.fromkeys(ancestors))
        return ancestors

    def get_children(self, lineage: str, network : OrderedDict = None):
        if not network:
            network = self.network
        return network[lineage]["children"]

    def get_depth(self, lineage: str, network : OrderedDict = None):
        return network[lineage]["depth"]

    def get_descendants(self, lineage: str, network : OrderedDict = None):
        '''
        Get all descendants between lineage and all tips.
        '''

        if not network:
            network = self.network

        descendants = []
        children = network[lineage]["children"]
        if len(children) == 0:
            return []
        for child in network[lineage]["children"]:
            child_descendants = self.get_descendants(lineage=child, network=network)
            descendants += [child] + child_descendants
        # remove duplicates (python 3.7+ preserves order)
        descendants = list(dict.fromkeys(descendants))
        return descendants

    def get_mrca(self, lineages: [str], network: OrderedDict = None):
        '''
        Get most recent common ancestors
        '''

        if not network: 
            network = self.network

        # Make a pile of all ancestors, include lineages themselves in list
        ancestors_count = {l:1 for l in lineages}
        for lineage in lineages:
            lineage_ancestors = network[lineage]["ancestors"]
            for a in lineage_ancestors:
                if a not in ancestors_count:
                    ancestors_count[a] = 0
                ancestors_count[a] += 1

        # Filter down to ancestors observed in all lineages
        ancestors_shared = [a for a,count in ancestors_count.items() if count == len(lineages)]

        # If no shared ancestors?
        if len(ancestors_shared) == 0:
            return []
        
        # Add network depth to each ancestors
        ancestors_depth = {a:network[a]["depth"] for a in ancestors_shared}

        # Find the lineage with the highest depth value
        max_depth = max(ancestors_depth.values())
        ancestors = [a for a,d in ancestors_depth.items() if d == max_depth]

        return ancestors

    def get_parents(self, lineage: str, network : OrderedDict = None):
        if not network:
            network = self.network
        return network[lineage]["parents"]

    def get_paths(
            self, 
            start: str, 
            end: str, 
            network : OrderedDict = None, 
            direction: Direction = Direction.Unknown, 
            depth: int = 0,
        ):
        '''
        '''
        if not network:
            network = self.network

        # Recursion bottom out, found our target
        if start == end:
            return [[start]]
        
        # If we don't know the direction yet
        if direction == Direction.Unknown:
            # If end is an ancestor of start, we need to move towards the root
            if end in self.get_ancestors(network=network, lineage=start):
                direction = Direction.ToRoot
            # If end is a descendant of start, we need to move towards the tips
            elif end in self.get_descendants(network=network, lineage=start):
                direction = Direction.ToTips
            # Otherwise, unclear relationship for movement, stop now
            else:
                return []

        # Figure out where we should go next in our search
        next_nodes = []    
        if direction == Direction.ToRoot:
            parents = self.get_parents(network=network, lineage=start)
            next_nodes = [p for p in parents if p == end or end in self.get_ancestors(network=network, lineage=p)]
        elif direction == Direction.ToTips:
            children = self.get_children(network=network, lineage=start)
            next_nodes = [c for c in children if c == end or end in self.get_descendants(network=network, lineage=c)]

        # Recursively search and update paths
        paths = []
        for lineage in next_nodes:     
            next_paths = self.get_paths(network=network, start=lineage, end=end, direction=direction, depth=depth + 1)
            for p in next_paths:
                p = [start] + p
                paths.append(p)

        return paths

    def get_recombinants(self, descendants=False, network: OrderedDict = None):
        '''
        '''

        if not network:
            network = self.network

        recombinants = []
        for lineage, info in network.items():
            if len(info["parents"]) > 1:
                recombinants.append(lineage)
                if descendants:
                    recombinants += info["descendants"]

        return recombinants

    def parse_aliases(self, alias_key_path: str):
        '''
        Extract the aliases from the hierarchy and removing recombinants because they 
        are not really aliases, so much as the alias key is a specification of their 
        parent-child relationships.
        '''

        logging.info(f"Creating aliases.")
        with open(alias_key_path) as data: 
            alias_key = json.load(data)
            aliases = OrderedDict()
            for alias,lineage in alias_key.items():
                if lineage == '' or type(lineage) == list: continue
                aliases[alias] = {"uncompressed": lineage, "compressed": lineage}
                lineage_split = lineage.split(".")
                # Simple compression, since the lineage will always be 100% decompressed 
                # in the alias key
                match_found = False
                for i in range(1,len(lineage_split)):
                    prefix = ".".join(lineage_split[0:len(lineage_split)-i])
                    suffix = ".".join(lineage_split[len(lineage_split)-i:])
                    for a,info in aliases.items():
                        if info["uncompressed"] == prefix:
                            aliases[alias]["compressed"] = ".".join([a, suffix])
                            match_found = True
                            break
                    if match_found: break

        return aliases

    def parse_mpox_lineages(self, lineage_notes_path):
        '''
        Returns a list of designated mpox lineages from the lineage notes.
        '''

        lineages = []
        # Parse out lineages and parents from markdown
        with open(lineage_notes_path) as infile:
            lineage = None  
            for line in infile:
                line = line.strip()
                if line.startswith("## "):
                    lineage = line.replace("## ", "")
                    lineages.append(lineage)
                elif line.startswith("* parent: ["):
                    parent = line.replace("* parent: [", "").split("]")[0]
                    self.hierarchy[lineage] = parent

        return(lineages)

    def parse_sarscov2_lineages(self, lineage_notes_path):
        '''
        Returns a list of designated sars-cov-2 lineages from the lineage notes.
        '''
        lineages = []

        if self.organism == Organism.SARSCOV2:
            # The lineage notes file is a TSV table
            with open(lineage_notes_path) as table:
                # Locate the lineage column in the header
                header = table.readline().strip().split("\t")
                lineage_i = header.index("Lineage")
                for line in table:
                    lineage = line.strip().split("\t")[lineage_i]
                    # Skip over Withdrawn lineages (that start with '*')
                    if lineage.startswith('*'): continue
                    lineages.append(lineage)
        
        return lineages

    def parse_recombinants(self, alias_key_path):
        '''
        Returns recombinants and their parents.
        '''
        recombinants = {}
        with open(alias_key_path) as data:
            alias_key = json.load(data)
            for lineage, parents in alias_key.items():
                if type(parents) != list: continue
                parents_unique = []
                for p in parents:
                    p = p.replace("*", "")
                    if p not in parents_unique:
                        parents_unique.append(p)
                recombinants[lineage] = parents_unique
        
        return recombinants
              

    def to_dot(self, network: OrderedDict = None):
        """Convert network to graphviz DOT."""        

        if not network:
            network = self.network

        lines = []

        lines.append("digraph PangoNet {")
        lines.append("  rankdir=LR;")
        for lineage,info in network.items():
            if len(info["parents"]) == 0:
                lines.append(f"  \"{lineage}\";")
            else:
                for parent in info["parents"]:
                    length = (info["depth"] - network[parent]["depth"])
                    lines.append(f"  \"{parent}\" -> \"{lineage}\" [len = {length}];")
        lines.append("}")                    
        dot  = "\n".join(lines)
        return dot
    
    def to_freyja(self, network: OrderedDict = None):
        """Convert network to freyja lineage hierarchy yaml."""

        if not network:
            network = self.network
            
        lines = []

        for lineage,info in network.items():
            # Exclude the manual 'root' node
            if lineage == "root": continue
            lines.append(f"- name: {lineage}")
            uncompress = self.uncompress(lineage)            
            lines.append(f"  alias: {uncompress}")

            # 'children' in freyja actually refers to all descendants
            descendants = self.get_descendants(lineage)
            if len(descendants) > 0:
                lines.append(f"  children:")
                for child in descendants:
                    lines.append(f"    - {child}")

            parents = self.get_parents(lineage)
            if len(parents) > 1:
                lines.append(f"  recombinant_parents: {','.join(parents)}")
            elif len(parents) == 1 and parents[0] != 'root':
                lines.append(f"  parent: {parents[0]}")

        freyja  = "\n".join(lines)
        return freyja


    def to_json(self, network: OrderedDict = None, compact=False):
        """Convert network to JSON."""
        if not network:
            network = self.network

        # Compact down network objects to simpler lists
        if compact:
            network = copy.deepcopy(network)
            for lineage,info in network.items():
                network[lineage]["parents"]     = ", ".join(info["parents"])
                network[lineage]["children"]    = ", ".join(info["children"])
                network[lineage]["ancestors"]   = ", ".join(info["ancestors"])
                network[lineage]["descendants"] = ", ".join(info["descendants"])
        
        json_data = str(json.dumps(network, indent=4))
        return json_data


    def to_mermaid(self, network: OrderedDict = None):
        """Convert network to mermaid diagram."""        

        if not network:
            network = self.network
        lines = []

        lines.append("graph LR;")
        for lineage,info in network.items():
            for parent in info["parents"]:
                # Calculate the depth difference between the parent and lineage
                # Ex. B (1) --> B.1 (2) is diff=1, which means the arrow will be -->
                # Ex. BJ.1 (8) --> XBB (11) is diff=3, which means the arrow will be ---->
                depth_diff = (info["depth"] - network[parent]["depth"]) - 1
                arrow = "--" + ("-" * depth_diff) + ">"
                lines.append(f"  {parent}{arrow}{lineage};")

        mermaid = "\n".join(lines)
        return mermaid


    def to_newick(self, node: str=None, parent: str=None, processed:set=set(), depth:int=0, extended:bool=True):
        """Convert network to newick tree."""

        # If no root node given, use first node in the network
        if depth == 0:
            processed = dict()
            if not node:
                node = list(self.network.keys())[0]

        # Make all branches length of 1
        branch_length = 1

        children = self.network[node]["children"]
        parents = self.network[node]["parents"]

        # If we are using extended newick syntax, use special '#' syntax for recombinant nodes (ex. XBC#XBC)
        if extended:
            if len(parents) > 1:
                node = f"{node}#{node}"
        # If we are not using extended newick, we will handle recombinants with multiple parents
        # by simply assigning the recombinant as a child to the first parent encountered, all other 
        # parents will be skipped
        elif len(parents) > 1 and node in processed:
            return (None, processed)

        # Recursively call function on all children
        newick_children = []
        for child in children:
            # Skip this child if we've already processed the node -> child relationships
            if node in processed and child in processed[node]: continue
            newick_child, _processed_child = self.to_newick(node=child, parent=node, processed=processed, depth=depth+1, extended=extended)
            # Mark the node -> child relationship as processed
            if node not in processed:
                processed[node] = set()
            processed[node].add(child)
            if newick_child:
                newick_children.append(newick_child)

        # Add all children newicks as sister clades
        if len(newick_children) > 0:
            newick = f"({','.join(newick_children)}){node}:{branch_length}"
        # Otherwise, make simple single node newick
        else:
            newick = f"{node}:{branch_length}"

        # For the final iteration (at root level), set the root branch length to 0, to enable IcyTree tree layouts
        # If all branch lengths are same (ex. 1), IcyTree will only allow cladogram layout
        if depth == 0:
            newick += ";"
            newick = newick.replace(f":{branch_length};", ":0;")

        # On the last iteration, simply return the newick string
        if depth == 0:
            return newick
        # Otherwise, return both newick and nodes processed so far
        else:
            return (newick, processed)


    def to_table(self, sep="\t"):
        """Convert network to table."""

        header = sep.join(["lineage", "parents", "children", "recombinant", "recombinant_descendant"])
        rows   = [header]
        recombinant_descendants = self.get_recombinants(descendants=True)
        for lineage,info in self.network.items():
            row = [
                lineage,
                ", ".join(info["parents"]),
                ", ".join(info["children"]),
                True if lineage in self.recombinants else False,
                True if lineage in recombinant_descendants else False
            ]
            row = [str(r)for r in row]
            rows.append(sep.join(row))

        table = "\n".join(rows)
        return table

    def uncompress(self, lineage):
        '''
        Uncompress lineage name.
        '''

        if lineage not in self.lineages:
            raise Exception(f"Lineage {lineage} does not exist.")

        # Split nomenclature on '.'. ex. BC = B.1.1.529.1.1.1
        # [ 'B', '1', '1', '529', '1', '1', '1']
        lineage_split = lineage.split(".")
        prefix = lineage_split[0]
        if prefix in self.aliases:
            suffix = lineage_split[1:] if len(lineage_split) > 1 else []
            lineage_split = [self.aliases[prefix]["uncompressed"]] + suffix
            lineage = ".".join(lineage_split)
            
        return(lineage)

def get_cli_options():
    import argparse

    description = 'pangonet v0.1.0 | Create and manipulate SARS-CoV-2 pango lineages in a phylogenetic network.'
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('--organism',      help='Organism name.', choices=[o.value for o in Organism], required=True)
    parser.add_argument('--lineage-notes', help='Path to the lineage_notes.txt')
    parser.add_argument('--alias-key',     help='Path to the alias_key.json')
    parser.add_argument('--output-prefix', help='Output prefix', default="pango")
    parser.add_argument('--output-all',    help='Output all formats', action="store_true")
    parser.add_argument('--tsv',           help='Output metadata TSV', action="store_true")
    parser.add_argument('--json',          help='Output json', action="store_true")    
    parser.add_argument('--nwk',           help='Output newick tree', action="store_true")
    parser.add_argument('--enwk',          help='Output extended newick tree for IcyTree', action="store_true")
    parser.add_argument('--mermaid',       help='Output mermaid graph', action="store_true")
    parser.add_argument('--dot',           help='Output dot for graphviz', action="store_true")
    parser.add_argument('--freyja',        help='Output lineages hierarchy for freyja.', action="store_true")
    parser.add_argument('-v', '--version', help='Print version', action="store_true")

    return parser.parse_args()

def cli():

    options = get_cli_options()

    if options.version:
        print("pangonet v0.1.0")
        sys.exit(0)

    logging.info(f"Begin") 

    # Check output directory based on prefix
    outdir = os.path.dirname(options.output_prefix)
    if outdir != "" and outdir != "." and not os.path.exists(outdir):
        logging.info(f"Creating output directory: {outdir}")        
        os.makedirs(outdir)

    # Create the network from the alias key and lineage notes, will download the files if not given
    pango = PangoNet().build(organism=options.organism, alias_key=options.alias_key, lineage_notes=options.lineage_notes, outdir=outdir)

    # -------------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------------

    # Table (for IcyTree)
    if options.output_all or options.tsv:
        table_path = options.output_prefix + ".tsv"
        logging.info(f"Exporting table: {table_path}")
        table = pango.to_table()
        with open(table_path, 'w') as outfile:
            outfile.write(table + "\n")

    # Standard newick
    if options.output_all or options.nwk:
        newick_path = options.output_prefix + ".nwk"
        logging.info(f"Exporting standard newick: {newick_path}")
        newick = pango.to_newick(extended=False)
        with open(newick_path, 'w') as outfile:
            outfile.write(newick + "\n")

    # Extended newick
    if options.output_all or options.enwk:
        newick_path = options.output_prefix + ".enwk"
        logging.info(f"Exporting extended newick: {newick_path}")
        newick = pango.to_newick(extended=True)
        with open(newick_path, 'w') as outfile:
            outfile.write(newick + "\n")

    # Mermaid
    if options.output_all or options.mermaid:
        mermaid_path = options.output_prefix + ".mermaid"
        logging.info(f"Exporting mermaid: {mermaid_path}")        
        mermaid = pango.to_mermaid()
        with open(mermaid_path, 'w') as outfile:
            outfile.write(mermaid + "\n")

    # Dot
    if options.output_all or options.dot:    
        dot_path = options.output_prefix + ".dot"
        dot = pango.to_dot()
        logging.info(f"Exporting dot: {dot_path}")
        with open(dot_path, 'w') as outfile:
            outfile.write(dot + "\n")

    # JSON
    if options.output_all or options.json:    
        json_path = options.output_prefix + ".json"
        logging.info(f"Exporting json: {json_path}")
        json_data = pango.to_json()
        with open(json_path, 'w') as outfile:
            outfile.write(json_data + "\n")

        json_path = options.output_prefix + ".compact.json"    
        logging.info(f"Exporting compact json: {json_path}") 
        json_data = pango.to_json(compact=True)
        with open(json_path, 'w') as outfile:
            outfile.write(json_data + "\n")

    # Freyja Lineage Hierarchy
    if options.output_all or options.freyja:
        freyja_path = options.output_prefix + ".lineages.yml"
        freyja = pango.to_freyja()
        logging.info(f"Exporting freyja: {freyja_path}")
        with open(freyja_path, 'w') as outfile:
            outfile.write(freyja + "\n")

    logging.info(f"Done") 

if __name__ == "__main__":
    cli()
