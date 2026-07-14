from pathlib import Path

_SAMPLE_ROWS = """query,item_name,item_id,final_answer,category4_name,category3_name,category2_name,category1_name
кола,кола,1,e,газировка,,,напитки
кола,кола,1,e,газировка,,,напитки
сок,сок,2,s,соки,,,напитки
вода,вода,3,i,вода питьевая,,,напитки
стул,стул,4,e,стулья,,,мебель
"""


def write_sample_csv(path: Path) -> None:
    path.write_text(_SAMPLE_ROWS, encoding="utf-8")
