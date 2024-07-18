#!/usr/bin/env python3

import sys
import urllib.request
from collections import OrderedDict
import json
import os
import copy
import logging

ALIAS_KEY_URL     = "https://raw.githubusercontent.com/cov-lineages/pango-designation/master/pango_designation/alias_key.json"
LINEAGE_NOTES_URL = "https://raw.githubusercontent.com/cov-lineages/pango-designation/master/lineage_notes.txt"

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format='%(asctime)s %(levelname)s:%(message)s')

class PangoNet:

    def __init__(self, alias_key: str = None, lineage_notes: str = None, root: str = "root"):
        '''
        root: If not None, manually create top level node with this name
        '''

        self.aliases = dict()
        self.hierarchy = OrderedDict()
        self.network = OrderedDict()
        self.root = root        
        self.lineages = list()

    def build(self, alias_key: str = None, lineage_notes: str = None, root: str = "root", outdir: str = None):

        if outdir and outdir != "" and outdir != "." and not os.path.exists(outdir):
            os.makedirs(outdir)
        # Download alias key if not provided
        if not alias_key:
            alias_key_path = self.download_alias_key(outdir=outdir)
        else:
            alias_key_path = alias_key
        
        # Download lineage notes if not provided
        if not lineage_notes:
            lineage_notes_path = self.download_lineage_notes(outdir=outdir)
        else:
            lineage_notes_path = lineage_notes

        self.lineages     = self.parse_lineages(lineage_notes_path)
        self.aliases      = self.parse_aliases(alias_key_path)
        self.recombinants = self.parse_recombinants(alias_key_path)
        self.network      = self.create_network()

        return self

    def compress(self, lineage):
        '''
        Compress lineage name
        '''

        # Decompress fully first
        lineage_compress = self.decompress(lineage)
        # Split nomenclature on '.'. ex. BC = B.1.1.529.1.1.1
        # [ 'B', '1', '1', '529', '1', '1', '1']
        lineage_split = lineage_compress.split(".")
        if len(lineage_split) <= 4:
            return(lineage)

        # Pango lineages have a maximum of four pieces before they need to be aliased
        # Keep compressing it until it's the right size
        while len(lineage_split) > 4:
            length = len(lineage_split)
            for i in range(1, length):
                prefix = ".".join(lineage_split[0:length - i])
                suffix = lineage_split[length - i:]   
                # Stop at the first alias encounter
                if prefix in self.aliases.values():
                    prefix_alias = [alias for alias,lineage in self.aliases.items() if lineage == prefix]
                    lineage_split = prefix_alias + suffix
        # Join the split pieces back together with the '.'
        alias = ".".join(lineage_split)
        return alias

    def decompress(self, lineage):
        '''
        Decompress lineage name.
        '''

        # Split nomenclature on '.'. ex. BC = B.1.1.529.1.1.1
        # [ 'B', '1', '1', '529', '1', '1', '1']
        lineage_split = lineage.split(".")
        # Pango lineages have a maximum of four pieces before they need to be aliased
        # Keep compressing it until it's the right size
        prefix = lineage_split[0]
        if prefix in self.aliases:
            suffix = lineage_split[1:] if len(lineage_split) > 1 else []
            lineage_split = [self.aliases[prefix]] + suffix
            lineage = ".".join(lineage_split)
        return(lineage)           

    def parse_aliases(self, alias_key_path: str):
        '''
        Extract the aliases from the hierarchy and removing recombinants because they 
        are not really aliases, so much as the alias key is a specification of their 
        parent-child relationships.
        '''

        logging.info(f"Creating aliases.")
        with open(alias_key_path) as data: 
            alias_key = json.load(data)
            aliases = {alias:lineage for alias,lineage in alias_key.items() if lineage != '' and type(lineage) != list}
        return aliases

    def parse_lineages(self, lineage_notes_path):
        '''
        Returns a list of designated lineages from the lineage notes.
        '''
        lineages = []

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
              

    def create_network(self):
        '''
        root : If not None, manually create top level node with this name
        '''
        logging.info(f"Creating network.")

        network = OrderedDict()
        # Manually add a root node according to params
        if self.root:
            network[self.root] = {"decompressed": "", "depth": 0, "parents": [], "children": [], "ancestors": [], "descendants": [], "depth": 0}
        root = self.root

        # ---------------------------------------------------------------------
        # Iteration #1: Parents

        for lineage in self.lineages:

            decompressed = self.decompress(lineage)
            decompressed_split = decompressed.split(".")

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
                decompressed = self.decompress(lineage)
                # Option 3: Top level node, A or B
                if "." not in decompressed:
                    parents = [self.root]
                else:
                    decompressed_parent = decompressed_split[0: (len(decompressed_split) - 1)]
                    parents = [self.compress(".".join(decompressed_parent))]

            network[lineage] = {"decompressed": decompressed, "depth": 0, "parents": parents, "children": [], "ancestors": [], "descendants": []}
    
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
        # Iteratation #5: Decompressed aliases

        lineages = list(network.keys())
        for lineage in lineages:
            decompressed = network[lineage]["decompressed"]
            if decompressed and decompressed != '' and decompressed not in network:
                network[decompressed] = network[lineage]

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
                depth = len(info["decompressed"].split("."))
            network[lineage]["depth"] = depth

        return network

    def download_alias_key(self, url: str = ALIAS_KEY_URL, outdir: str = None):
        alias_key_path = os.path.basename(url)
        if outdir:
            alias_key_path = os.path.join(outdir, alias_key_path)
        logging.info(f"Downloading alias key: {alias_key_path}")      
        urllib.request.urlretrieve(url, alias_key_path)
        return alias_key_path

    def download_lineage_notes(self, url: str = LINEAGE_NOTES_URL, outdir: str = None):
        lineage_notes_path = os.path.basename(url)
        if outdir:
            lineage_notes_path = os.path.join(outdir, lineage_notes_path)
        logging.info(f"Downloading lineage notes: {lineage_notes_path}")        
        urllib.request.urlretrieve(url, lineage_notes_path)
        return lineage_notes_path

    def filter(self, lineages: [str], network: OrderedDict = None):
        '''
        Filter network to only the specified lineages.
        '''

        if not network:
            network = self.network
        
        # Keep order of lineages in network
        lineages = [l for l in network if l in lineages]
        pango_net = copy.deepcopy(self)    

        filtered_network = OrderedDict()        
        for lineage in lineages:
            info = network[lineage]
            filtered_network[lineage] = copy.deepcopy(network[lineage])
            filtered_network[lineage]["parents"]     = [l for l in info["parents"]     if l in lineages]
            filtered_network[lineage]["children"]    = [l for l in info["children"]    if l in lineages]
            filtered_network[lineage]["ancestors"]   = [l for l in info["ancestors"]   if l in lineages]
            filtered_network[lineage]["descendants"] = [l for l in info["descendants"] if l in lineages]

        pango_net.network = filtered_network
        # Update attributes
        pango_net.recombinants = self.get_recombinants()
        return pango_net

    def get_parents(self, lineage: str, network : OrderedDict = None):
        if not network:
            network = self.network
        return network[lineage]["parents"]

    def get_children(self, lineage: str, network : OrderedDict = None):
        if not network:
            network = self.network
        return network[lineage]["children"]

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

    def to_mermaid(self, network: OrderedDict = None):

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

    def to_dot(self, network: OrderedDict = None):

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

    def to_table(self, sep="\t"):
        '''
        Create tsv table.
        '''

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

    def to_json(self, network: OrderedDict = None, compact=False):
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

    def to_newick(self, node: str=None, parent: str=None, processed:set=set(), depth:int=0, extended:bool=True):
        '''
        Convert network to newick.
        '''

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

def get_cli_options():
    import argparse

    description = 'Create and manipulate SARS-CoV-2 pango lineages in a phylogenetic network.'
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('--lineage-notes', help='Path to the lineage_notes.txt')
    parser.add_argument('--alias-key',     help='Path to the alias_key.json')
    parser.add_argument('--output-prefix', help='Output prefix', default="pangonet")
    parser.add_argument('--output-all',    help='Output all formats', action="store_true")
    parser.add_argument('--tsv',           help='Output metadata TSV', action="store_true")
    parser.add_argument('--json',          help='Output json', action="store_true")    
    parser.add_argument('--nwk',           help='Output newick tree', action="store_true")
    parser.add_argument('--enwk',          help='Output extended newick tree for IcyTree', action="store_true")
    parser.add_argument('--mermaid',       help='Output mermaid graph', action="store_true")
    parser.add_argument('--dot',           help='Output dot for graphviz', action="store_true")
    parser.add_argument('-v', '--version',       help='Print version', action="store_true")

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
    pango_net = PangoNet().build(alias_key=options.alias_key, lineage_notes=options.lineage_notes, outdir=outdir)

    # -------------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------------

    # Table (for IcyTree)
    if options.output_all or options.tsv:
        table_path = options.output_prefix + ".tsv"
        logging.info(f"Exporting table: {table_path}")
        table = pango_net.to_table()
        with open(table_path, 'w') as outfile:
            outfile.write(table + "\n")

    # Standard newick
    if options.output_all or options.nwk:
        newick_path = options.output_prefix + ".nwk"
        logging.info(f"Exporting standard newick: {newick_path}")
        newick = pango_net.to_newick(extended=False)
        with open(newick_path, 'w') as outfile:
            outfile.write(newick + "\n")

    # Extended newick
    if options.output_all or options.enwk:
        newick_path = options.output_prefix + ".enwk"
        logging.info(f"Exporting extended newick: {newick_path}")
        newick = pango_net.to_newick(extended=True)
        with open(newick_path, 'w') as outfile:
            outfile.write(newick + "\n")

    # Mermaid
    if options.output_all or options.mermaid:
        mermaid_path = options.output_prefix + ".mermaid"
        logging.info(f"Exporting mermaid: {mermaid_path}")        
        mermaid = pango_net.to_mermaid()
        with open(mermaid_path, 'w') as outfile:
            outfile.write(mermaid + "\n")

    # Dot
    if options.output_all or options.dot:    
        dot_path = options.output_prefix + ".dot"
        dot = pango_net.to_dot()
        logging.info(f"Exporting dot: {dot_path}")
        with open(dot_path, 'w') as outfile:
            outfile.write(dot + "\n")

    # JSON
    if options.output_all or options.json:    
        json_path = options.output_prefix + ".json"
        logging.info(f"Exporting json: {json_path}")
        json_data = pango_net.to_json()
        with open(json_path, 'w') as outfile:
            outfile.write(json_data + "\n")

        json_path = options.output_prefix + ".compact.json"    
        logging.info(f"Exporting compact json: {json_path}") 
        json_data = pango_net.to_json(compact=True)
        with open(json_path, 'w') as outfile:
            outfile.write(json_data + "\n")

    logging.info(f"Done") 

if __name__ == "__main__":
    cli()
