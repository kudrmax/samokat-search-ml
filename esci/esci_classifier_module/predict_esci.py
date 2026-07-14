import sys
import joblib
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

MODEL_DIR = BASE_DIR / "model_package"
E5_DIR = str((MODEL_DIR / "e5_model").resolve())

_stage1_pipeline = joblib.load(MODEL_DIR / "stage1_pipeline.joblib")
_stage2_pipeline = joblib.load(MODEL_DIR / "stage2_pipeline.joblib")

for pipe in (_stage1_pipeline, _stage2_pipeline):
    preprocessor = pipe.named_steps['preprocessor']
    for name, transformer in preprocessor.transformer_list:
        if hasattr(transformer, 'model_dir'):
            transformer.model_dir = E5_DIR

_CODE_TO_LABEL = {0: "I", 1: "C", 2: "S", 3: "E"}


def predict_esci(query: str, item_name: str) -> str:
    x = pd.DataFrame({"query": [query], "item_name": [item_name]})

    stage1_pred = _stage1_pipeline.predict(x)[0]
    if stage1_pred == 0:
        return "I"

    stage2_pred = _stage2_pipeline.predict(x)[0]
    return _CODE_TO_LABEL[stage2_pred]


if __name__ == "__main__":
    print(predict_esci("энергетик без сахара", "энергетик самокат, без сахара, с соком малины, 0,33 л"))