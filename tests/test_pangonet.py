from pangonet import PangoNet
import os

# Version controlled data files for testing expected values
data_dir      = os.path.join(os.getcwd(), "tests", "data")
sarscov2_alias_key     = os.path.join(data_dir , "sars-cov-2","alias_key_2024-07-19.json")
sarscov2_lineage_notes = os.path.join(data_dir , "sars-cov-2", "lineage_notes_2024-07-19.txt")
mpox_alias_key     = os.path.join(data_dir , "mpox", "alias_key_2024-09-06.json")
mpox_lineage_notes = os.path.join(data_dir , "mpox", "lineages_2024-09-06.md")

# New files for testing latest compatibility
sarscov2_new_dir           = os.path.join(os.getcwd(), "tests", "sars-cov-2")
sarscov2_new_alias_key     = os.path.join(sarscov2_new_dir, "alias_key.json")
sarscov2_new_lineage_notes = os.path.join(sarscov2_new_dir, "lineage_notes.txt")

mpox_new_dir           = os.path.join(os.getcwd(), "tests", "mpox")
mpox_new_alias_key     = os.path.join(mpox_new_dir, "alias_key.json")
mpox_new_lineage_notes = os.path.join(mpox_new_dir, "lineages.md")

def test_pangonet_init():
    pango = PangoNet()

def test_pangonet_bfs():
    ...

def test_pangonet_build_sarscov2():
    pango = PangoNet().build(organism="sars-cov-2", outdir=sarscov2_new_dir)

def test_pangonet_build_mpox():
    pango = PangoNet().build(organism="mpox", outdir=mpox_new_dir)

def test_pangonet_compress_sarscov2():
    pango = PangoNet().build(organism="sars-cov-2", alias_key=sarscov2_new_alias_key, lineage_notes=sarscov2_new_lineage_notes)
    assert pango.compress("BA.1")                == "BA.1"
    assert pango.compress("XBB.1.2")             == "XBB.1.2"
    assert pango.compress("XBC")                 == "XBC"
    try:
        pango.compress("B.1.1.529.1.1.1.4.5")
        assert False
    except Exception as e:
        assert str(e) == "Alias BC.4.5 of lineage B.1.1.529.1.1.1.4.5 does not exist."  

def test_pangonet_compress_mpox():
    pango = PangoNet().build(organism="mpox", alias_key=mpox_new_alias_key, lineage_notes=mpox_new_lineage_notes)
    assert pango.compress("A.1.1.1") == "B.1"
    try:
        pango.compress("C.1.19")
        assert False
    except Exception as e:
        assert str(e) == "Alias C.1.19 of lineage C.1.19 does not exist."

def test_pangonet_dfs_sarscov2():
    pango = PangoNet().build(organism="sars-cov-2", alias_key=sarscov2_alias_key, lineage_notes=sarscov2_lineage_notes)
    assert pango.dfs(start="BA.1.1.1") == ['BA.1.1.1', 'BC.1', 'BC.2']

def test_pangonet_dfs_mpox():
    pango = PangoNet().build(organism="mpox", alias_key=mpox_alias_key, lineage_notes=mpox_lineage_notes)
    assert pango.dfs(start="B.1.3") == ['B.1.3', 'C.1', 'C.1.1']

def test_pangonet_filter():
    ...

def test_pangonet_get_ancestors():
    ...

def test_pangonet_get_children_sarscov2():
    pango = PangoNet().build(organism="sars-cov-2", alias_key=sarscov2_alias_key, lineage_notes=sarscov2_lineage_notes)
    assert pango.get_children("JN.1.1") == ['JN.1.1.1', 'JN.1.1.2', 'JN.1.1.3', 'JN.1.1.4', 'JN.1.1.5', 'JN.1.1.6', 'JN.1.1.7', 'JN.1.1.8', 'JN.1.1.9', 'JN.1.1.10', 'XDN', 'XDR']

def test_pangonet_get_children_mpox():
    ...

def test_pangonet_get_descendants():
    ...

def test_pangonet_get_mrca_sarscov2():
    pango = PangoNet().build(organism="sars-cov-2", alias_key=sarscov2_alias_key, lineage_notes=sarscov2_lineage_notes)
    assert pango.get_mrca(["BA.1", "BA.2", "BC.1"]) == ["B.1.1.529"]
    assert pango.get_mrca(["BA.1.2", "XD"]) == ["BA.1"]
    assert pango.get_mrca(["XE", "XG"]) == ["BA.1", "BA.2"]
    assert pango.get_mrca(["BA.1", "BA.1.1"]) == ["BA.1"]
    assert pango.get_mrca(["XBB.1", "XBL"]) == ["XBB.1"]

def test_pangonet_get_mrca_mpox():
    pango = PangoNet().build(organism="mpox", alias_key=mpox_alias_key, lineage_notes=mpox_lineage_notes)
    assert pango.get_mrca(["A.1.1", "A.2"])    == ["A"]
    assert pango.get_mrca(["B.1.19", "C.1.1"]) == ["B.1"]

def test_pangonet_get_parents_sarscov2():
    pango = PangoNet().build(organism="sars-cov-2", alias_key=sarscov2_new_alias_key, lineage_notes=sarscov2_new_lineage_notes)
    assert pango.get_parents("BA.1")    == ["B.1.1.529"]
    assert pango.get_parents("XBB")     == ['BJ.1', 'BM.1.1.1']
    assert pango.get_parents("XBB.1.5") == ['XBB.1']

def test_pangonet_get_parents_mpox():
    pango = PangoNet().build(organism="mpox", alias_key=mpox_new_alias_key, lineage_notes=mpox_new_lineage_notes)
    assert pango.get_parents("A.2.2")    == ["A.2"]
    assert pango.get_parents("B.1")     == ["A.1.1"]
    assert pango.get_parents("C.1")     == ["B.1.3"]

def test_pangonet_get_paths_sarscov2():
    pango = PangoNet().build(organism="sars-cov-2", alias_key=sarscov2_new_alias_key, lineage_notes=sarscov2_new_lineage_notes)
    # Going towards root
    assert pango.get_paths(start="BA.1", end="BA.1")  == [["BA.1"]]
    assert pango.get_paths(start="BA.1", end="B.1.1") == [["BA.1", "B.1.1.529", "B.1.1" ]]
    assert pango.get_paths(start="XE",   end="B.1")   == [
        ['XE', 'BA.1', 'B.1.1.529', 'B.1.1', 'B.1'], 
        ['XE', 'BA.2', 'B.1.1.529', 'B.1.1', 'B.1']
    ]
    # Going towards root, recursive recombination    
    assert pango.get_paths(start="XBL",  end="B.1.1") == [
        ['XBL', 'XBB.1.5.57', 'XBB.1.5', 'XBB.1', 'XBB', 'BJ.1', 'BA.2.10.1', 'BA.2.10', 'BA.2', 'B.1.1.529', 'B.1.1'],
        ['XBL', 'XBB.1.5.57', 'XBB.1.5', 'XBB.1', 'XBB', 'BM.1.1.1', 'BM.1.1', 'BM.1', 'BA.2.75.3', 'BA.2.75', 'BA.2', 'B.1.1.529', 'B.1.1'],
        ['XBL', 'BA.2.75', 'BA.2', 'B.1.1.529', 'B.1.1']
    ]

def test_pangonet_get_paths_mpox():
    pango = PangoNet().build(organism="mpox", alias_key=mpox_new_alias_key, lineage_notes=mpox_new_lineage_notes)
    # Going towards root
    assert pango.get_paths(start="A.2.3", end="A")   == [["A.2.3", "A.2", "A"]]
    assert pango.get_paths(start="C.1", end="A.1.1") == [["C.1", "B.1.3", "B.1", "A.1.1"]]

    # Going towards tips
    assert pango.get_paths(start="A", end="A.2.3")   == [["A", "A.2", "A.2.3"]]
    assert pango.get_paths(start="A.1.1", end="C.1") == [["A.1.1", "B.1", "B.1.3", "C.1"]]

    # Going sideways, nope?
    assert pango.get_paths(start="A.1.1", end="A.2")  == []

def test_pangonet_get_recombinants():
    ...

def test_pangonet_to_dot():
    ...

def test_pangonet_to_json():
    ...

def test_pangonet_to_mermaid():
    ...

def test_pangonet_to_newick():
    ...

def test_pangonet_to_table():
    ...

def test_pangonet_uncompress_sarscov2():
    pango = PangoNet().build(organism="sars-cov-2", alias_key=sarscov2_new_alias_key, lineage_notes=sarscov2_new_lineage_notes)
    assert pango.uncompress("BA.1")    == "B.1.1.529.1"
    assert pango.uncompress("XBB.1.2") == "XBB.1.2"
    assert pango.uncompress("XBC")     == "XBC"
    try:
        pango.uncompress("BC.4.5")
        assert False
    except Exception as e:
        assert str(e) == "Lineage BC.4.5 does not exist."

def test_pangonet_uncompress_mpox():
    pango = PangoNet().build(organism="mpox", alias_key=mpox_new_alias_key, lineage_notes=mpox_new_lineage_notes)
    assert pango.uncompress("A.1")   == "A.1"
    assert pango.uncompress("B.1")   == "A.1.1.1"
    assert pango.uncompress("B.1.2") == "A.1.1.1.2"
    assert pango.uncompress("C.1.1") == "A.1.1.1.3.1.1"
    try:
        pango.uncompress("C.1.19")
        assert False
    except Exception as e:
        assert str(e) == "Lineage C.1.19 does not exist."
