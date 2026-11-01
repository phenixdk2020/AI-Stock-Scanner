"""Eksempelaktier fra ni børser. Noteringssted er ikke altid hjemland."""

SAMPLES = {
    "Danmark": ("NOVO-B.CO", "DSV.CO", "VWS.CO", "MAERSK-B.CO"),
    "Tyskland": ("SAP.DE", "SIE.DE", "ALV.DE", "BMW.DE"),
    "Sverige": ("VOLV-B.ST", "ATCO-A.ST", "ERIC-B.ST", "INVE-B.ST"),
    "Norge": ("EQNR.OL", "DNB.OL", "NHY.OL", "MOWI.OL"),
    "USA": ("MSFT", "NVDA", "AAPL", "GOOGL"),
    "Frankrig": ("MC.PA", "OR.PA", "SAN.PA", "AIR.PA"),
    "Holland": ("ASML.AS", "INGA.AS", "AD.AS", "HEIA.AS"),
    "Spanien": ("SAN.MC", "IBE.MC", "ITX.MC", "BBVA.MC"),
    "Finland": ("NOKIA.HE", "KNEBV.HE", "FORTUM.HE", "SAMPO.HE"),
}


def market_of(ticker: str) -> str:
    ticker = ticker.upper()
    for suffix, country in (
        (".CO", "Danmark"), (".DE", "Tyskland"),
        (".ST", "Sverige"), (".OL", "Norge"),
        (".PA", "Frankrig"), (".AS", "Holland"),
        (".MC", "Spanien"), (".HE", "Finland"),
    ):
        if ticker.endswith(suffix):
            return country
    return "USA" if "." not in ticker and not ticker.startswith("^") else "Andet/ukendt"


SUPPORTED_MARKETS = frozenset(SAMPLES)
ETF_SAMPLES = ("VWCE.DE", "EUNL.DE", "SXR8.DE", "VWRL.AS")


def instrument_type_of(ticker: str) -> str:
    """Kun eksplicit kendte ETF-symboler klassificeres automatisk."""
    return "ETF" if ticker.upper() in ETF_SAMPLES else "Ukendt"


def example_tickers(markets: list[str], include_etfs: bool = False) -> list[str]:
    tickers = [ticker for market in markets for ticker in SAMPLES[market]]
    if include_etfs:
        tickers.extend(ETF_SAMPLES)
    return list(dict.fromkeys(tickers))
