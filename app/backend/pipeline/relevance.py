import sys
from pathlib import Path


class RelevanceClassifier:
    """Адаптер над модулем esci_classifier_module (модуль не меняем)."""

    def __init__(self, module_parent: Path) -> None:
        module_dir = module_parent / "esci_classifier_module"
        if not (module_dir / "predict_esci.py").exists():
            raise RuntimeError(
                f"Модуль esci_classifier_module не найден в {module_parent}."
            )
        parent = str(module_parent.resolve())
        if parent not in sys.path:
            sys.path.insert(0, parent)
        from esci_classifier_module.predict_esci import predict_esci

        self._predict_esci = predict_esci

    def predict(self, query: str, item_name: str) -> str:
        return self._predict_esci(query, item_name)

    def is_exact(self, query: str, item_name: str) -> bool:
        return self.predict(query, item_name) == "E"
