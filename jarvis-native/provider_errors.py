"""Safe public provider errors and bounded rate-limit recovery."""

import re


class ProviderBusy(RuntimeError):
    def __init__(self, seconds):
        self.seconds = max(1, min(86400, seconds))
        super().__init__(
            f"Groq alcanzó su cuota temporal. Espera unos {self.seconds:.0f} segundos "
            "y vuelve a intentarlo. Tu petición no se reiniciará automáticamente."
        )


def retry_delay(error):
    headers = getattr(getattr(error, "response", None), "headers", {})
    try:
        if headers.get("retry-after"):
            return max(0.1, float(headers["retry-after"]))
        if headers.get("retry-after-ms"):
            return max(0.1, float(headers["retry-after-ms"]) / 1000)
    except (ValueError, TypeError):
        pass
    match = re.search(r"try again in\s+([\d.]+)\s*([smh])", str(error), re.I)
    if match:
        return float(match[1]) * {"s": 1, "m": 60, "h": 3600}[match[2].lower()]
    return 60
