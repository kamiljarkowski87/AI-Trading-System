"""Pobieranie raportów finansowych z SEC EDGAR (darmowe, bez klucza API)."""
import httpx
from trading.logging.decision_logger import log

HEADERS = {"User-Agent": "AI Trading Bot kamiljarkowski87@gmail.com"}

TICKER_TO_CIK = {
    "AAPL": "0000320193",
    "NVDA": "0001045810",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "AMZN": "0001018724",
    "TSLA": "0001318605",
    "META": "0001326801",
}


async def get_recent_filings(ticker: str, form_types: list[str] = None) -> str:
    """Pobiera ostatnie raporty finansowe dla danej akcji."""
    if form_types is None:
        form_types = ["10-K", "10-Q", "8-K"]

    cik = TICKER_TO_CIK.get(ticker.upper())
    if not cik:
        return f"Brak danych SEC dla {ticker}"

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15) as client:
            r = await client.get(f"https://data.sec.gov/submissions/CIK{cik}.json")
            data = r.json()

        company_name = data.get("name", ticker)
        filings = data.get("filings", {}).get("recent", {})

        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        descriptions = filings.get("primaryDocDescription", [])

        results = []
        for form, date, desc in zip(forms, dates, descriptions):
            if form in form_types:
                results.append(f"{date} | {form} | {desc or 'Raport finansowy'}")
            if len(results) >= 5:
                break

        if not results:
            return f"Brak niedawnych raportów {', '.join(form_types)} dla {company_name}"

        summary = f"SEC EDGAR — {company_name} ({ticker}):\n"
        summary += "\n".join(results)
        log.info("sec_filings.fetched", ticker=ticker, count=len(results))
        return summary

    except Exception as e:
        log.warning("sec_filings.error", ticker=ticker, error=str(e))
        return f"Błąd pobierania SEC filings dla {ticker}: {e}"


async def get_latest_filing_summary(ticker: str) -> str:
    """Pobiera treść ostatniego raportu 10-Q lub 10-K i zwraca kluczowe dane."""
    cik = TICKER_TO_CIK.get(ticker.upper())
    if not cik:
        return ""

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15) as client:
            r = await client.get(f"https://data.sec.gov/submissions/CIK{cik}.json")
            data = r.json()

        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        accessions = filings.get("accessionNumber", [])

        for form, date, acc in zip(forms, dates, accessions):
            if form in ["10-Q", "10-K"]:
                acc_clean = acc.replace("-", "")
                url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{acc}.txt"
                log.info("sec_filings.latest", ticker=ticker, form=form, date=date)
                return f"Ostatni raport {form} z dnia {date} dla {ticker}. Accession: {acc}"

    except Exception as e:
        log.warning("sec_filings.summary_error", ticker=ticker, error=str(e))

    return ""
