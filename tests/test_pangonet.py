from pangonet import PangoNet
import os

# Version controlled data files for testing expected values
data_dir      = os.path.join(os.getcwd(), "tests", "data")
alias_key     = os.path.join(data_dir , "alias_key_2024-07-19.json")
lineage_notes = os.path.join(data_dir , "lineage_notes_2024-07-19.txt")

# New files for testing new compatibility
new_dir            = os.path.join(os.getcwd(), "tests", "output")
new_alias_key     = os.path.join(new_dir, "alias_key.json")
new_lineage_notes = os.path.join(new_dir, "lineage_notes.txt")

def test_pangonet_init():
    pango = PangoNet()

def test_pangonet_build():
    pango = PangoNet().build(outdir=new_dir)

def test_pangonet_compress():
    pango = PangoNet().build(alias_key=new_alias_key, lineage_notes=new_lineage_notes)
    assert pango.compress("BA.1")                == "BA.1"
    assert pango.compress("B.1.1.529.1.1.1.4.5") == "BC.4.5"
    assert pango.compress("XBB.1.2")             == "XBB.1.2"
    assert pango.compress("XBC")                 == "XBC"

def test_pangonet_filter():
    ...

def test_pangonet_get_ancestors():
    ...

def test_pangonet_get_children():
    pango = PangoNet().build(alias_key=alias_key, lineage_notes=lineage_notes)
    assert pango.get_children("JN.1.1") == ['JN.1.1.1', 'JN.1.1.2', 'JN.1.1.3', 'JN.1.1.4', 'JN.1.1.5', 'JN.1.1.6', 'JN.1.1.7', 'JN.1.1.8', 'JN.1.1.9', 'JN.1.1.10', 'XDN', 'XDR']

def test_pangonet_get_descendants():
    ...

def test_pangonet_get_mrca():
    pango = PangoNet().build(alias_key=alias_key, lineage_notes=lineage_notes)
    assert pango.get_mrca(["BA.1", "BA.2", "BC.1"]) == ["B.1.1.529"]
    assert pango.get_mrca(["BA.1.2", "XD"]) == ["BA.1"]
    assert pango.get_mrca(["XE", "XG"]) == ["BA.1", "BA.2"]
    assert pango.get_mrca(["BA.1", "BA.1.1"]) == ["BA.1"]
    assert pango.get_mrca(["XBB.1", "XBL"]) == ["XBB.1"]

def test_pangonet_get_parents():
    pango = PangoNet().build(alias_key=new_alias_key, lineage_notes=new_lineage_notes)
    assert pango.get_parents("BA.1")    == ["B.1.1.529"]
    assert pango.get_parents("XBB")     == ['BJ.1', 'BM.1.1.1']
    assert pango.get_parents("XBB.1.5") == ['XBB.1']

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

def test_pangonet_uncompress():
    pango = PangoNet().build(alias_key=new_alias_key, lineage_notes=new_lineage_notes)
    assert pango.uncompress("BA.1")    == "B.1.1.529.1"
    assert pango.uncompress("BC.4.5")  == "B.1.1.529.1.1.1.4.5"
    assert pango.uncompress("XBB.1.2") == "XBB.1.2"
    assert pango.uncompress("XBC")     == "XBC"
