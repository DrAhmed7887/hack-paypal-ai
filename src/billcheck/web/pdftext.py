"""Extract text from an uploaded PDF in a separate process with a time and page limit (hostile files can't hang
the web server). Run as: python -I -m billcheck.web.pdftext  < file.pdf  > text"""

import io
import subprocess
import sys

MAX_PAGES = 10
TIMEOUT_S = 10


def extract_text(raw: bytes) -> str:
    try:
        done = subprocess.run([sys.executable, "-I", "-m", "billcheck.web.pdftext"], input=raw,
                              capture_output=True, timeout=TIMEOUT_S, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("the PDF took too long to read") from exc
    if done.returncode != 0:
        raise ValueError("the PDF could not be read")
    return done.stdout.decode("utf-8", errors="replace")


def _main() -> int:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(sys.stdin.buffer.read()))
    if len(reader.pages) > MAX_PAGES:
        return 2
    sys.stdout.write("\n".join((p.extract_text() or "") for p in reader.pages))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
