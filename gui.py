"""Trading Agents — web GUI (AFK-style pro terminal).

    python3 gui.py            opens the dashboard in your browser
    python3 gui.py --no-open  serve only, print the address
    python3 gui.py --port 9000

Standard library only — nothing to install, same promise as the rest
of this repo. The dashboard runs on YOUR machine only (127.0.0.1):
it reads brain.json, draws the chart from real Yahoo Finance candles,
and its buttons run the same commands you would type in a terminal
(main.py learn / backtest) and stream their output live.

Paper trading only — simulated money, no broker connected.
"""
import json
import os
import subprocess
import sys
import threading
import base64
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.join(HERE, "brain.json")
LOGO = os.path.join(HERE, "docs", "logo.png")
LOGO_B64 = (
    "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"
    "3g+pR3usw8jSmXUSjZ2WletgyOVf/jm+rmqjiPzo0tQIHyzLnyNLNx90PgVB6h+t4xt5UvnO2FFkfelhSnyRCqpzn29leN/x1orP"
    "plxjqf9prsasF4U839dDnnuee7G5hoF+VKjIW2Znc4qt4uR/LNMprRCVBsxzt0p+m3k8d3JrDDkfMibjt+/QWovsAv2iEERZhRfr"
    "86ow///3S/otda33NsQvHlIU3/7Y83e7/010Pw6aPp4+8w+qyzOskUciYGqd9TIdFIKoraR/WGEqxJiK5Yu7naow+KAnlQaHRl5s"
    "JP1hhcL0xf39ccRx4Toe1VVarT5g6enHOh9qLJ1XcKXz8j+VPuJyacoQRimUcX5axo/VBXUfRP7Uujd1ecTj6f4vFeplz+rKpzgf"
    "8eWT1KU7/yOFIcupx3x6fXT37b0/6Lw+LM1fF8Vl/CgZG2GxUag3fXd6ztiAOT7HXzKf/dnd7gv4h1iDZF8P95QOxVTa9sbkvzHr"
    "ac4N6e+rfz5lHs+NsPMN9KkyZq9Ql7HnWvlk71sl/98cj1WvfTtQ34O6l/SvSPrj6nrLH92PJfBcK3MuwX6TeTz3heUaJ14yj+eO"
    "P9dgkAuYx8wRGZLraRzz/Vih8ahwAR0Uzsv/Juk/Vii0/qykf0YhsxrTM4br6hsa9CDpb0v6P9WlRRueaQtXmFSGFl9/ccH0ED2W"
    "Csi/U0hXfzT6bCq77bNF3Syfe5P0l9VVOHP5n+XvfQVyLE5fn6LHUkH5P61uARZLz5a+GLK+rLhy6Idy/q+S/q7SFSX7HTf4Kbr/"
    "lPjbFDaq4kVdxeyflfQPnB6LFwfDsuK8w65vv47ELyT9JYVg50enxy3v8J1FNmLDByKH6P7fc597iH7b5/pG7aO6Bud/VNJP3OfK"
    "Pc8/H8uJGwulcO7+jqT/WdLvi56fGzExNSD/FN2P3z8XP1in6KUBebwmVByUW0DdFxD/MPP+XzX8HcXxS/z/xx2eqe9naASVxSp9"
    "/+P/KOk/l/RXdX49Pqr7bovVDsil8xW3N5L+ZUl/StI/pPPMLu4lzyWoXEBcOiQ8LrBrv3/pkI7SoGTqkNHU51uPks0z3ikEUX9Z"
    "0r9zevy/lvRPKVzAvtcDbejL9Gyo6F7h/Nr15s+jGWqh7cv04oA+DpgsQ/yqbqGkvUJA9yqGhbbuTV06eVXIT7/T+POWa8GXhns1"
    "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"
    "Sm+V3+N3jNL0Zc+xtG3vaT/kUdcVf997hWvfX++vp/vf6vy82e146PGSaqTPNesrK2rto13j9fG17usn10o/cdkqST9QSOdx/oS2"
    "HNSVaVa+7Ua+dkz9B3eOHnIAANCC1MicWw9msRwCIQBNICAHAABLSo2A2bgfoFTfNCyCcgCLIyAHAACt8AESATlqa219FABgDjkA"
    "AFhUX9BtczZbR6NB2+gZB9C0NRR0AADg9sUL7W1EPQV1pHrGCcoBNIGCDgAALGloaDq9zwCAm8aQdQAA0CLmkKM2esUBNIeAHLUc"
    "Tr8/Jx6jQrW8vkqIPze2L6uNnLlmxcWGpn6V9OI+347l4J4Xvw7Li9ON7as71z6/U8/7QdKX029La7aXLPuQL++obp9fu2/zx5/V"
    "7WUfL/h2zf2jDwr7Dttn7tQd873vQz6mfFmanSv7/aKuXLmWvrnsvuHJrgV2GajHf7ep37nRwlZeSOf51LO6NOXfr+/zgF4MWccc"
    "KERQgsILtZGm1onzBmBp5EOYHT3kAFpxHHEbwO3pu8bZogpAqdojOMiTUB095Kgl1StOTzmmoqDDnOKGHtJbe/xwTxu+CwBL6ht+"
    "ThmCKughR22pAPyac/2wTql5vARMqMWnJSpU7fFzL31eQEAOoFScx9fqGafsQDUE5JgDPeO4hA+YGLIO3CdfdtAoB2BpBOKYHUPW"
    "UUtfEE5gjiko6DAnKlZt6lt9mh5yAKX6GvamdB4NrXMBFCMgx5wIxgG0iopUmyg3ALSK0XuYBUPWYUorQakWSPtbjQpWrTlASDso"
    "7Mtq36vtu/mgbg/gOdk+v4+n44jnlNJ42Da/37j/8Y/lXj+k9Hp/k/RR3R7ktpcs6aoNG4W8Ji4zdrpO/pPj9yDfKeSNr2J9lLWw"
    "fb1tz/iNwnncXenz432ppS4f2rvbu+gYx+xxj7y+fH7Kd/t0+m351Ebd3uSMvEIxKiMAPAoWXGIT/W5Nq8cFAADuHAE5AKC21gPg"
    "1o/vXtEACAC4OwTkAICaNj23WxEfU4vHeG/65mWyyjoA4OYRkAOQ3s/57duzGUjZ6P2Kta0NY08dXyvHBgJxAMCdIiAHANTWWqBL"
    "r/g6EIQDAO4OATkAoKbWg12C8/YM7fFLkA4AuGkE5ABiVIBRS8vBbsvHds8IwgEAd4V9yGFK9wG2PTNfFfZmPKrbV9P2AC1B5blM"
    "/P2lzvde53tJ9z1vzPtPZZ+5V9iLXOr2Qrc9WlOfQ7pog6WTw+n2D9TtKT9mr+ZrnMc3dfta+/19byENtfD9ThEfr+3xbeWIlSH2"
    "96XXtPD54lHhGB8Ujq/GWgRrO39r48/RQV1dZWz+VCq1r7jViz7N/Nmox6eVmouX0gAJesgBADfPB1MAAADNoIccAHBPbjEopwcV"
    "AObVtz0jUIwecgDAPaNiBQAYkionKDtQDT3kAIBbFw9Z9xUpepexNNIg0C5bA8Bux/eBYgTkAIB7cosVqFxAd4v/MwBcE0PWMRuG"
    "rAMA7hkVKwDAEIasY1YE5ACAe0RlCgAALI4h6xhrTOV1L+nD6bY19hx6notlpfYlH9oWau45jht1ew5v1e09/qDz+VqxW9pLumW5"
    "69/Okf38Ut2+37Y3+ZL8MVj6WvqYalr7/3JUtz+07c8shX2it+ryBjuP/rrfaHo5c2l+Ya97PP28SXq68L1QX3wd+Pu2v/3udP9V"
    "Xb5Vev2MnTJy0Hk5J0nfKaTzR3cslj/55+N6Ut/3TiHNWJkmhfMGVEEPOWraRL/tNsEScD+oPKIW0hJu2VAjOIA7QkCOWuKgmyB8"
    "fVINKZxHjEXFEnMgXeEWka4B/H0E5KiNAA6AoQcIY6Qa/0g3uEXx9oukcwAE5KgqHrJOD+t6pKYbAGPFFUwqmrhEvLcv6Qi3oK/B"
    "ifQNQBKLuqGeoSHrNRZNwfxSDSk0qmAsrnFcijwG94QGJwBn6CFHbVSsABgqmyhBwIJbR/oGQEAOAJgVFU4AAIAeDFlHLXuF9PR4"
    "um97SO/FsOeWDO3T+vH02+/5K9U5d7n32Cjs6fugbg9W25PY9iee8n5rM3Yf21bEx9P6NW77DW8V9pK12/4xXE9qPu02etzu237R"
    "/jz5aVB+3/I5+X2sN6fjsmPBsvryR78mge0hvT/97VHd3tJzn0Ofdu32g0KZt+97ERaTSg+2J7zlA3tJzzrPf/rqV2PqP6nX4Y7Q"
    "Qw4AAJbWeiX02HMbAIAiBOQAWhMvKEcPFHA/hkbxtIDAfH3icoQyBUBTGLIOoAVDq/TfAyr2uGepILzFBd1SwXhrx4hhcWB+b2UN"
    "gAbRQw6gJVSOgPvTt499K0F56732GIdecgBNIiAH0IpN4jc9GMB96OtxbiX4TR1fK8eGYQxZB9A0hqwDaAFD1ofd2/eB+7KWIese"
    "Q9bXKTVknXMIYFH0kANoCYEnAAAA7gY95KhpJ+kXOt9T+kHdftZYTirQ9XujbhX21Nyo21dz6+7PzT7zRd0+6NL9DFmf+38s3Se1"
    "7/1S7/Ogbu/opc5dasTFUd2e9rbXfeq5uD6/D/nu9Htzuv1lkSM6t1O3D7Hf05pOjXWwa99f659Pv6+1j31clvlRIHYMe/c8S29Y"
    "ni83rT70oO78lE6zYYQGKExQVWqYIRlNOy49F9c6h6QdAGtDgw5wf7juURU95KjF90ChPbkW3DgQ7utRvbalPx/AdfgKbmvlSJwP"
    "xQtQArhtXOuYFQE5ajqoq0ixUEq7xvZCLznkGMD96MtnWl7YjV0ggPvA3vWYHQE5ajoozIGKe1jJvNoxFIz7yu+1K8GpfYhJQ8B9"
    "SK123doq5vSSA/DGrtLfSh6GhhGQoybfQ24IptqwhiHrre4/DOA6+oLyltBbBtyfe9+aFTNjUTfUZAE5QXjbxga+LVaGAaAFBOPA"
    "/eG6xywIyFETq2SvzxrO0RqOEcDlhiq5rV//VM6B28Y1jtkxZB012f7jfl6N/43l5OZjp+ZDjp0fNUbuPWz/aktDfl/ijeo3Hk4d"
    "Hp/7/Nyq0KXvP+X18dzbo873dvbs/v6C9/f3H06/HxXO3yeF7+Th9POWef+5bRX+RztPtu+vpTcrC/u+n7UHhWs4fjs31rC7Uzg3"
    "XzWcPq9RtvjFSm0P8l93j/m61CXfdemq8rnvIPf+c3fOlKa/qfljfN/v6e0X4+urA0893tz3b3uMS+F/sZGEW53nz7vosb3Yi7wV"
    "vsMpV14CkxGQA2iBVUDilYutASEX0OUqLbm5qaUBcU5ppWpMhW/osdoNAn3vlzp/rQeDQI41Cu4U0vOTQuPTg7ogKjYl3ddskLvE"
    "mAbTks/PvX8uf8+9Ps5fUwvw+UCYLVoBNIWAHEALLIizSu9O571mc/cAlVZIc+buQU8tpuiVBPTSeYU31bDx5m5bI4q9ZwsV36Hv"
    "l9E7yLEALk5He4Ue88fEa3y6yl3fpT1upflXacBdevxjGlSH9DW2xrf9wrM0FAJoBgE5gBbYdnk2rPigbjjfGKUVulzQOGVI9yWf"
    "X7NymHqv3PeT+3z//aQqvA86P287deevlSkrqf+xhePCOvjRHluFNP94+unLH1qZ8pBL57n8rfT4577OUlOyUruF+IZf/7P0+QFw"
    "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"
    "8flRvK+zEvdbR/q7bb4M3ev8fD+py48eTo9bnmTXAJZl58Juvymcq2edj+KJ88G15UNYEBc6AOCeHHtuo00EqwCAm0YPOQAAmNPY"
    "oJrgG8Ca0KiLKughBwDcOipN68JibgBacdT7qXuUKaiKgBwAcA98hSq+jWX5AJyVqAG0irIDs2DIOgDgntDLcX0lQ9YJygG0ijIE"
    "VdBDDgC4dVSaAACXSA1ZB6oiIAcA3AMqU+uxEfPIAbSL8gRVMWQdtX3S+b6+1qpI408b+vbL3CnsqekLma1up9BZ+v/IBRZLH9+t"
    "2yikcdvPWnp/Dcwpd35L08fSgWvf549N10d1ezBvFfYat/zng7q9mf3n2X3bu3zN5k4fWFZqf+qtQrp+UJeeD+6xzek+5mffc9/6"
    "FXED4Sb6ia8/rkdMRpAEIIV5tgAA4B5MbdRbeyMgGkMPOQCPll6gvtLKG5U/AJhHnL+m7vf1hgNVEJCjltS2NcwBXI/UgiUUPAAA"
    "4F5M3XaROi6qYMg6akvtJYt1IRAHAAD3ZEwwnup8AorRQw4gxS/MB6DM3Iu20YgGAJe5ZMg69SNURQ85akoNWcc6MGQdAADcs1xw"
    "nns+cBF6yFFLXyZGZgUAAIA1of6KqyEgRy2WcX09/bb9NNei9X1+c8Z81/GwK/+zlfSm8/lRO4V9UlFuTdfCLdqffg7q9q22aRkt"
    "7ENe+vq5h7RfY8j8/vQ59tvypa96vx9zvCf5rSP/WLetunNo+Y79/kbdaNWNQrnr86aDGM16TX1bvsbn7Sjpk9grHpVwkaMWKgzr"
    "ERcynDsArSFvAgDcBQJy1EawBwAo0ddLBQDAzWHIOuYydYGwexh2uDS/OiiNJUBn7fnT2q9lv3qx8VNqAAC4WQTkqOkY/Y7/XuO9"
    "+7ReYV6a38aMUQwA1oD8CWh/DYmcuY+f+h9Wj4ActaSCcatMkVkCAMaIyxICcgDATSMgx1wYst4eP2Td3wfu3drzp7UfPwAAd4tF"
    "3YD7RDAOoGX0kAMA7gI95Bgr18NyULdvtd22Bh/bV7bk/f3jfYv/lMg1TuXev/TxWt9P39SBvtf7hZPeFM7b7vTYW+Yzp5i7h27p"
    "Svs19mnG5R7VnaP96f5W0qtCfpXb1zq312xp+h6TfuLnTPnM0vRZ+njOTuFcbE8/bwr1ky/u76l9nP19L76/9Bxc3LZc+rE0bfuM"
    "H9TlKdvTbUvTVl+y93zQ/Okvl//tE49dM//JyeUBueNP1S/9Mb2pqyNu3f1npY99av4DEJCjmk8K6WmvLrN6VVcA5Yyp8A4Ngx/T"
    "YDAkF3yOKXDnNLZCmTpO++420fN8xfZZXWOK1BVgwK3wjVbPkp7UVYbj50zVd32OrZiNqbD2TTlJ5Y2p15fI5Qe5PD73/72cPuOD"
    "ugrv8fS+T2MOEGhYHORZWXyQ9NU9b6Pzctqu+9z1V9qg740JMONgNpe/5OpXY+qIQ+L6Xd/x9gXh9v32rV/xQaE+++L+PlTnAiYj"
    "IEct3yukJ9/Laj1PW5UXKPFz4lXDc6/PZfi5x3MBd43/b0hphdta4O1YjurOT1zg70e8H7AmB4V0vVeXP1ne5CvANQz1IvXtr51r"
    "MMy9b07ues7lb7mgOPf+Y/LHjdKjqqjwYu2GgtxnhXrTQefXoZXR/rlT3t/L5S+PE18/9ZrM5R9j8r+cMSOI+hoxH6LHU7dt1Ked"
    "l4O6cwcUIyBHLVbB3Slk7i8KGZZl9KUFhteXaQ4p7UHPVShzFdoaBc6Q1GgB/z8/6H2DhvUOHhVaf61SEH9Xj6fHgbXaqivvtgpp"
    "2nphrSExNqVRKu697gsm+3pgxuZPlwblpfnT3CNm4oqunZdrfDYwt/g6t+DbyuA3nQ+Lnqp0BJ/v+Y0dNT1gj83dYZEbip47vtzj"
    "XyR9c7odd2A8qfv+gIsRkKMmq0i9SPqVup6oF9VfBTh+v1zAWDokKmfuOaZjCzwfCMRD3+zv1ivuK79xgW3TD2xuObBmX9Sl8686"
    "HwLuK1iXNPZJ59ePnw6S4j936sJlU4ape6UV4rmHxFvjiI1kkLpz9bXvRcBKpMpYKZSzB3UN4vacnXvdmDK4dA0cXz9KNRb6+lUq"
    "4C39/NJGt1TD5lCeNvUxazTZK/SKW2PKs+isQCUE5KjF5v/Z4knfqhum9KLyDDs3hzz3+lymmbsW5g6oS8Vzmvzwz/i7s7lrPmD/"
    "oq4BZe8eP6q8sg0s7bO66TTW22PzAm3RMOl9mr+kB3toCPwx8SPlK6Q+f0pdzzmlDYalI4zG1DWst3B3+rw3hXPzccRrgdb5ctfu"
    "HyV9p244tI0U8YHumM6E0hF8pq+x0B/3pY2Cc/L/fyoo3w08Jr2vS8b53UeFPMxGWu0UgnEbCcq0GhQjIEctVtH965L+3On2B0m/"
    "VLe66JDnCZ+VCsS/y7wmV6kr7cHPDVn6XPj5XzKP/+D02wJxPzd2o3Au/Gf53qijpL8l6W+494gD9lYKXuAST5L+oqRfU7gW9uqG"
    "GtqInrgy6u/nrv9Pp9+bnp/4fePP+EXm/X/dvb8St3NyQ05z+e+UBoOUXP5n39Oru23rkvzNzGuBNfBrtlgaf5H0O5L+vMKQaFt7"
    "x1/bO5XXn77JPP47p9+pvE9636ERH8+3mffP9fBPqf/1vf/QHPIfZx5/TvzN335Stwio5XVfFeq73yhfPwOyNscj9WyMMqbyd5T0"
    "Q3XD1C0g/0blw55TgeGURZFKV0EvvVBKRwjkWIFkAbn/7XvLzSH6+UZdoWyBir12jgVXals6Iysd8osyY77/PyDptxQar17UrXsh"
    "dddHKlgeE5D7rYqmBuS29saQ3BzJnJpreKSULpopddOdrAfqO0m/T9L/rfOtn1K/S68/rl+UmJJ+rMH8QSGo+02FetIndSND/OvG"
    "BOSlDWb2mX2NkrH4eGqMgCwRv3/f+/XlnXEPe/y8V51vnfmm0Lj7LOlnA5/Xd3zAOwTkqKV0yCMJcVml3//SQ7bWnn5qV0juzdzp"
    "79YDvrWnv6U/H/dt6fJv7ddv6/njVGs7XjRg7r2TAQAAAABAAgE5AAAAAAALICAHAAAAAGABrLIOAACGMCcSAICZ0EMOAAAAAMAC"
    "CMgBAAAAAFgAATkAAAAAAAtgDjmuZek5iGvfZ7vU3N//0ud3bkvv83rr32+p1r+f3PGtfR/znNaPDxjSevm/9uur9eNv/fhwA+gh"
    "BwAAAABgAQTkAAAAAAAsgIAcAAAAAIAFMIcct4I5PgDmcuv5y63/f8AtW3oNitbn2APNo4ccAAAAAIAFEJADAAAAALAAAnIAAAAA"
    "ABbAHHKMVToHiTlGy1r7PsZLK03ffP9l1v79lR5/6/8fgH5Lz/Em/xjG94PF0UMOAAAAAMACCMgBAAAAAFgAATkAAAAAAAsgIAcA"
    "AAAAYAEE5AAAAAAALOD/BzN1phdYp5StAAAAAElFTkSuQmCC"
)

try:
    from config import CONFIG
    SYMBOLS = CONFIG.get("symbols", [])
except Exception:
    SYMBOLS = []
if not SYMBOLS:
    SYMBOLS = ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN",
               "GOOGL", "META", "AMD", "NFLX", "JPM"]

# ---------------------------------------------------------------- state
_lock = threading.Lock()
_proc = None            # running main.py subprocess, or None
_proc_label = ""
_log_lines = []         # last 300 lines of subprocess output
_candle_cache = {}      # symbol -> (fetched_at, payload)


def _read_brain():
    try:
        with open(BRAIN) as f:
            return json.load(f)
    except Exception:
        return {}


def state_payload():
    b = _read_brain()
    acc = b.get("account", {}) or {}
    pos = acc.get("positions", {}) or {}
    last = acc.get("last_prices", {}) or {}
    risk = acc.get("open_risk", {}) or {}
    positions = []
    pos_value = 0.0
    for sym, p in pos.items():
        lp = last.get(sym)
        if lp is None:
            continue
        val = p["qty"] * lp
        pos_value += val
        r = risk.get(sym, {}) or {}
        positions.append({
            "symbol": sym, "qty": p["qty"], "avg": p["avg_price"],
            "last": lp, "value": val,
            "stop": r.get("stop_loss"), "target": r.get("take_profit"),
            "entry": r.get("entry"),
        })
    cash = acc.get("cash", 0.0)
    with _lock:
        running = _proc is not None and _proc.poll() is None
        label = _proc_label if running else ""
        log = list(_log_lines[-60:])
    return {
        "cash": cash,
        "equity": cash + pos_value,
        "pnl": acc.get("realised_pnl", 0.0),
        "days": b.get("days_learned", 0),
        "trades": b.get("total_trades", 0),
        "positions": positions,
        "prices": last,
        "weights": b.get("weights", {}),
        "boss": b.get("boss", {}),
        "symbols": SYMBOLS,
        "running": running,
        "running_label": label,
        "log": log,
    }


TIMEFRAMES = {
    "5m": ("5d", "5m", 400),
    "1h": ("3mo", "60m", 400),
    "1d": ("6mo", "1d", 120),
}


def candles_payload(symbol, tf="5m"):
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        symbol = SYMBOLS[0]
    if tf not in TIMEFRAMES:
        tf = "5m"
    rng, interval, keep = TIMEFRAMES[tf]
    now = time.time()
    key = (symbol, tf)
    hit = _candle_cache.get(key)
    if hit and now - hit[0] < 60:
        return hit[1]
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{symbol}?range={rng}&interval={interval}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = json.load(resp)
    result = raw["chart"]["result"][0]
    q = result["indicators"]["quote"][0]
    rows = []
    for t, o, h, l, c, v in zip(result["timestamp"], q["open"], q["high"],
                                q["low"], q["close"], q["volume"]):
        if None in (o, h, l, c):
            continue
        rows.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v or 0})
    payload = {"symbol": symbol, "tf": tf, "rows": rows[-keep:]}
    _candle_cache[key] = (now, payload)
    return payload


# ------------------------------------------------------------ processes
def _pump(proc):
    global _proc
    try:
        for line in proc.stdout:
            with _lock:
                _log_lines.append(line.rstrip())
                del _log_lines[:-300]
    except Exception:
        pass
    finally:
        with _lock:
            if _proc is proc:
                _proc = None


def start_process(args, label):
    global _proc, _proc_label
    with _lock:
        if _proc is not None and _proc.poll() is None:
            return False, "already running: " + _proc_label
        _log_lines.append(f"--- {label}: {' '.join(args)} ---")
    proc = subprocess.Popen(
        [sys.executable, os.path.join(HERE, "main.py")] + args,
        cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1)
    with _lock:
        _proc, _proc_label = proc, label
    threading.Thread(target=_pump, args=(proc,), daemon=True).start()
    return True, label + " started"


def stop_process():
    global _proc
    with _lock:
        proc = _proc
    if proc is None or proc.poll() is not None:
        return False, "nothing is running"
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except Exception:
        proc.kill()
    with _lock:
        _log_lines.append("--- stopped by user (brain is saved; nothing is lost) ---")
    return True, "stopped"


# ---------------------------------------------------------------- page
PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>TRADING AGENTS · terminal</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
:root{--bg:#0d0e10;--bg2:#08090b;--panel:#121316;--line:#1e2024;--tx:#e8e9eb;--mut:#8b8e94;--up:#3fbf8f;--dn:#e5534b;--acc:#6d7cff;--btn:#1f3a2e;box-sizing:border-box;color-scheme:dark}
*,*::before,*::after{box-sizing:inherit}
body{margin:0;background:var(--bg);font:14px/1.3 Inter,system-ui,sans-serif;color:var(--tx);padding:0}
.mono{font-family:"JetBrains Mono",ui-monospace,monospace}
.up{color:var(--up)}.dn{color:var(--dn)}.mut{color:var(--mut)}
.app{width:100%;min-height:100vh;margin:0;background:var(--bg);overflow:hidden;display:flex;flex-direction:column}
header{display:flex;align-items:center;gap:28px;padding:14px 20px;background:var(--bg2);flex-wrap:wrap}
.logo{font-weight:800;font-size:22px;letter-spacing:-1px;display:flex;align-items:center;gap:10px}
.logo img{height:36px;width:auto;border-radius:6px}
nav{display:flex;gap:26px;color:var(--mut);flex-wrap:wrap}
nav a{cursor:pointer}nav a:hover{color:var(--tx)}
.hr{margin-left:auto;display:flex;gap:10px;align-items:center}
.pill{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:9px 14px;color:var(--mut);white-space:nowrap}
.pill.t{color:var(--tx)}
.ticker{display:flex;gap:24px;padding:10px 20px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);overflow-x:auto;white-space:nowrap;font-size:13px;scrollbar-width:none}
.ticker span{display:flex;align-items:center;gap:6px;cursor:pointer}
.av{width:20px;height:20px;border-radius:5px;display:inline-block}
.main{display:grid;grid-template-columns:1fr 380px}
.info{display:flex;align-items:center;gap:28px;padding:14px 20px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.tok{display:flex;gap:14px;align-items:center}
.tokimg{width:56px;height:56px;border-radius:8px;background:#000;border:1px solid var(--up);display:grid;place-items:center;overflow:hidden}
.tokimg img{width:100%;height:100%;object-fit:contain}
.big{font-size:30px;font-weight:600}
.stat small{display:block;color:var(--mut);margin-bottom:4px}.stat b{font-weight:500;font-size:15px}
.sp{margin-left:auto;display:flex;gap:28px}
.tf{display:grid;grid-template-columns:repeat(4,1fr);border-bottom:1px solid var(--line);border-left:1px solid var(--line);text-align:center;padding:18px 0}
.tf div{color:var(--mut);cursor:pointer}.tf b{display:block;margin-top:6px;font-weight:500}
.tf div.on{color:var(--tx)}.tf div.on span{color:var(--acc)}
.tb{display:flex;gap:18px;align-items:center;padding:12px 20px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.tb .r{margin-left:auto;display:flex;gap:18px;align-items:center}
.tb span.a{color:var(--acc)}
.tb .tfl{cursor:pointer}.tb .tfl.on{color:var(--acc)}
.chartwrap{display:flex;height:520px;position:relative}
.tools{width:50px;display:flex;flex-direction:column;gap:8px;align-items:center;padding:10px 0;color:var(--mut);font-size:18px}
.tools i{font-style:normal;width:34px;height:34px;display:grid;place-items:center;border-radius:6px;cursor:pointer}.tools i:hover{background:var(--panel);color:var(--tx)}
.cv{flex:1;position:relative;min-width:0}
canvas{position:absolute;inset:0;width:100%;height:100%}
.leg{position:absolute;left:14px;top:8px;z-index:2;font-size:15px}
.leg .o span{margin-right:8px;font-size:13px}
.tfoot{display:flex;gap:16px;padding:10px 70px 10px 58px;border-top:1px solid var(--line);color:var(--mut);align-items:center}
.tfoot .r{margin-left:auto}
.tabs{display:flex;gap:28px;padding:16px 20px 0;border-top:1px solid var(--line);color:var(--mut);align-items:center;flex-wrap:wrap}
.tabs .on{color:var(--tx);border-bottom:2px solid var(--tx);padding-bottom:12px}
.tabs .r{margin-left:auto;display:flex;gap:8px;padding-bottom:10px}
.tag{padding:6px 10px;border-radius:6px;font-size:12px;font-weight:600}
.tag.g{background:#10261d;color:var(--up)}.tag.y{background:#2b2410;color:#e7b94d}
.tblw{overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:720px}
th{text-align:left;color:var(--mut);font-weight:400;padding:12px 20px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);font-size:13px}
td{padding:16px 20px}
tbody tr:nth-child(even){background:#101114}
.log{background:var(--bg2);border-top:1px solid var(--line);padding:12px 20px;font-family:"JetBrains Mono",ui-monospace,monospace;font-size:12.5px;color:#c9d4de;height:140px;overflow-y:auto;white-space:pre-wrap}
aside{border-left:1px solid var(--line);padding:0}
.side{padding:16px}
.seg{display:grid;grid-template-columns:1fr 1fr;background:var(--panel);border-radius:8px;padding:3px;gap:3px;color:var(--mut);text-align:center;font-size:13px}
.seg div{padding:8px;border-radius:6px;cursor:pointer}.seg .on{background:#25272b;color:var(--tx)}
.bs{margin-top:12px}.bs div{padding:12px;font-size:15px}.bs .on{background:var(--btn);color:var(--up)}
.in{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px;margin-top:12px;display:flex;justify-content:space-between;color:var(--mut)}
.q{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:10px}
.q button{background:var(--panel);border:1px solid var(--line);color:var(--tx);border-radius:6px;padding:10px 0;font:inherit;cursor:pointer;font-size:12px}
.q button:hover{border-color:var(--up)}
.go{margin-top:14px;background:var(--btn);color:var(--up);border:1px solid #2b5642;border-radius:8px;padding:14px;display:flex;justify-content:space-between;cursor:pointer;width:100%;font:inherit}
.fees{display:flex;gap:14px;color:var(--mut);margin:14px 0;font-size:13px;align-items:center}
.fees .r{margin-left:auto}
.row{display:flex;align-items:center;gap:8px;margin-top:8px}
.box{flex:1;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px;display:flex;justify-content:space-between;color:var(--mut)}
.box b{color:var(--tx);font-weight:400}
.sec{display:flex;justify-content:space-between;padding:16px;border-top:1px solid var(--line);margin-top:6px}
.sim{margin:0 16px 16px;background:var(--panel);border-radius:8px;padding:10px;display:flex;gap:12px;align-items:center}
.sim .tokimg{width:48px;height:48px;font-size:16px}
footer{display:flex;gap:22px;align-items:center;padding:12px 20px;background:var(--bg2);color:var(--mut);border-top:1px solid var(--line);flex-wrap:wrap}
footer .r{margin-left:auto;display:flex;gap:18px;align-items:center}
.sw{width:42px;height:22px;border-radius:12px;background:#25272b;display:inline-block;vertical-align:middle;margin-right:8px;position:relative}.sw::after{content:"";position:absolute;left:3px;top:3px;width:16px;height:16px;border-radius:50%;background:#111}
@media(max-width:1000px){.main{grid-template-columns:1fr}aside{border-left:0;border-top:1px solid var(--line)}.sp{margin-left:0}.chartwrap{height:420px}.tools{display:none}.tfoot{padding:10px 16px}}
@media(max-width:600px){body{padding:6px}nav{display:none}.big{font-size:24px}}
</style>
</head>
<body>
<div class="app">
  <header>
    <div class="logo"><img src="/logo.png" alt="logo">TRADING AGENTS</div>
    <nav><a>Dashboard</a><a>Learn</a><a>Backtest</a><a>Live</a><a>Council</a></nav>
    <div class="hr"><div class="pill">Day <b id="daychip" style="color:var(--tx)">–</b></div><div class="pill t" id="eqpill">Equity –</div><div class="pill t">Danyal Malik</div></div>
  </header>
  <div class="ticker mono" id="tk"></div>

  <div class="main">
    <section>
      <div class="info">
        <div class="tok"><div class="tokimg"><img src="/logo.png" alt="logo"></div><div><b style="font-size:16px" id="symname">AAPL</b> <span class="mut">held by the crew</span><div class="mut" style="margin-top:6px">Yahoo Finance · real data</div></div></div>
        <div class="big" id="bigprice">$–</div>
        <div class="stat"><small>Cash</small><b id="st-cash">–</b></div>
        <div class="stat"><small>Equity</small><b id="st-eq">–</b></div>
        <div class="stat"><small>Realised P&amp;L</small><b id="st-pnl">–</b></div>
        <div class="sp">
          <div class="stat"><small>Experience</small><b id="st-trades">–</b></div>
          <div class="stat"><small>Positions</small><b id="st-pos">–</b></div>
          <div class="stat"><small>Boss</small><b id="st-boss">–</b></div>
        </div>
      </div>
      <div class="tb">
        <span class="tfl on" data-tf="5m" onclick="setTF('5m')">5m</span><span class="tfl" data-tf="1h" onclick="setTF('1h')">1h</span><span class="tfl" data-tf="1d" onclick="setTF('1d')">1d</span><span>|</span><span>ƒx Indicators</span><span>▾ Display Options</span><span>Council view</span>
        <div class="r"><span>Yahoo Finance</span><span class="up">● Live</span></div>
      </div>
      <div class="chartwrap">
        <div class="tools"><i style="color:var(--acc)">+</i><i>╱</i><i>≡</i><i>⌖</i><i>≣</i><i>T</i><i>⊕</i><i>∩</i></div>
        <div class="cv"><div class="leg"><div><span id="ct">AAPL/USD · 5m · Yahoo Finance</span> <span class="up">●</span> <span class="o mono" id="ohlc"></span></div><div class="mut" style="margin-top:6px">Volume <span class="up mono" id="volspan">–</span></div></div><canvas id="c"></canvas></div>
      </div>
      <div class="tfoot"><span>5m</span><span>1h</span><span>1d</span><span>6mo</span><span class="r mono" id="clk">–</span></div>
      <div class="tabs"><span class="on">Positions</span><span>Orders</span><span>History</span><div class="r"><span class="tag g" id="statustag">OPERATIONAL</span><span class="tag y">PAPER TRADING ONLY</span></div></div>
      <div class="tblw"><table class="mono">
        <thead><tr><th>Symbol</th><th>Qty</th><th>Avg price</th><th>Last</th><th>Value</th><th>Stop</th><th>Target</th></tr></thead>
        <tbody id="posbody"></tbody></table></div>
      <div class="log" id="log">Press START LEARNING — the crew's output will stream here, exactly like the terminal.</div>
    </section>

    <aside>
      <div class="tf"><div class="on" data-tf="5m" onclick="setTF('5m')"><span>5m</span><b id="tf-5m">–</b></div><div data-tf="1h" onclick="setTF('1h')"><span>1h</span><b id="tf-1h">–</b></div><div data-tf="1d" onclick="setTF('1d')"><span>1d</span><b id="tf-1d">–</b></div><div><span>Day</span><b id="tf-day" style="color:var(--tx)">–</b></div></div>
      <div class="side">
        <div class="seg"><div class="on">Council</div><div>Risk Guard</div></div>
        <div class="seg bs"><div class="on" id="btn-start" onclick="act('start')">START LEARNING</div><div id="btn-stop" onclick="act('stop')">Stop</div></div>
        <div style="margin-top:14px">Council vote today</div>
        <div class="in"><span id="bossline">Boss — strategy</span><span id="bosspct" style="color:var(--tx)">–</span></div>
        <div class="q" id="wchips"></div>
        <button class="go" id="btn-bt" onclick="act('backtest')"><span>Run Backtest</span><span>full history</span></button>
        <div class="fees"><span>Paper mode</span><span>No broker</span><span>Real data</span><span class="r pill" style="padding:4px 8px">Stdlib only</span></div>
        <div class="row"><span>Risk guard — selected position</span></div>
        <div class="row"><div class="box"><span>Entry</span><b id="rg-entry">–</b></div><div class="box"><span>Qty</span><b id="rg-qty">–</b></div></div>
        <div class="row"><div class="box"><span>↑ TP</span><b id="rg-target">–</b></div><div class="box"><span>Value</span><b id="rg-value">–</b></div></div>
        <div class="row"><div class="box"><span>↓ SL</span><b id="rg-stop">–</b></div><div class="box"><span>Avg</span><b id="rg-avg">–</b></div></div>
      </div>
      <div class="sec"><span>Held by the crew</span><span class="mut">⌄</span></div>
      <div id="simlist"></div>
      <div class="sec"><span>Council of 14 agents</span><span class="mut">⌄</span></div>
    </aside>
  </div>
  <footer><span>Trading Agents</span><span class="up" id="footstatus">● Operational — idle</span><span>▪ Council paper terminal</span>
    <div class="r"><span><i class="sw"></i>Paper</span><span>No broker connected</span><span>Real Yahoo data</span></div></footer>
</div>

<script>
let SYM = 'AAPL', TF = '5m', STATE = null;
const $ = id => document.getElementById(id);
const money = n => '$' + Math.round(n).toLocaleString('en-US');
const COLORS = ['#d8ff3d','#e0a33a','#6a8','#b66','#58a','#777','#ccc','#e94','#999','#a85'];

async function loadState() {
  const s = await (await fetch('/api/state')).json();
  STATE = s;
  $('daychip').textContent = s.days;
  $('eqpill').textContent = 'Equity ' + money(s.equity);
  $('st-cash').textContent = money(s.cash);
  $('st-eq').textContent = money(s.equity);
  const pnl = $('st-pnl');
  pnl.textContent = (s.pnl >= 0 ? '+' : '−') + money(Math.abs(s.pnl)).slice(0);
  pnl.textContent = (s.pnl >= 0 ? '+' : '-') + money(Math.abs(s.pnl)).replace('$-', '-$');
  pnl.className = s.pnl >= 0 ? 'up' : 'dn';
  $('st-trades').textContent = s.trades + ' trades';
  $('st-pos').textContent = s.positions.length;
  const bossName = (s.boss && s.boss.name) || '–';
  $('st-boss').textContent = bossName;
  $('tf-day').textContent = s.days;
  $('bossline').textContent = 'Boss — ' + bossName;
  const w = s.weights || {};
  const wv = k => w['w_' + k];
  $('bosspct').textContent = wv('strategy') ? Math.round(wv('strategy') * 100) + '% of the vote' : '–';
  $('wchips').innerHTML = ['strategy','history','pattern','regime','pressure'].map(k =>
    `<button>${k.slice(0,4).toUpperCase()} ${wv(k) ? Math.round(wv(k) * 100) + '%' : '–'}</button>`).join('');
  $('tk').innerHTML = s.symbols.map((sym, i) => {
    const p = s.prices[sym];
    const held = s.positions.some(x => x.symbol === sym);
    return `<span onclick="setSYM('${sym}')"><b style="font-weight:500;font-family:Inter;${held ? 'color:var(--up)' : ''}">${sym}</b><span class="mut">${p ? '$' + p.toFixed(2) : '–'}</span></span>`;
  }).join('');
  const fx = v => v == null ? '–' : '$' + v.toFixed(2);
  const pos = s.positions.find(x => x.symbol === SYM) || s.positions[0];
  if (pos) {
    $('rg-entry').textContent = fx(pos.entry);
    $('rg-qty').textContent = pos.qty;
    $('rg-target').textContent = fx(pos.target);
    $('rg-stop').textContent = fx(pos.stop);
    $('rg-avg').textContent = fx(pos.avg);
    $('rg-value').textContent = money(pos.value);
  }
  $('posbody').innerHTML = s.positions.map(p =>
    `<tr><td><b style="font-weight:500">${p.symbol}</b></td><td class="mut">${p.qty}</td><td class="mut">${fx(p.avg)}</td><td class="mut">${fx(p.last)}</td><td>$${Math.round(p.value).toLocaleString('en-US')}</td><td class="mut">${fx(p.stop)}</td><td class="mut">${fx(p.target)}</td></tr>`).join('');
  $('simlist').innerHTML = s.positions.map(p =>
    `<div class="sim"><div class="tokimg" style="font-size:13px;border-color:#333;color:var(--tx);font-weight:800">${p.symbol.slice(0, 2)}</div><div><div>${p.symbol} <span class="mut">${p.qty} shares</span></div><div class="up" style="margin-top:4px">${money(p.value)}</div></div></div>`).join('');
  const last = s.prices[SYM];
  if (last) $('bigprice').textContent = '$' + last.toFixed(2);
  $('symname').textContent = SYM;
  const run = s.running;
  $('statustag').textContent = run ? 'RUNNING' : 'OPERATIONAL';
  $('footstatus').textContent = run ? '● Operational — ' + s.running_label + ' running' : '● Operational — idle';
  $('btn-start').textContent = run ? 'RUNNING…' : 'START LEARNING';
  if (s.log && s.log.length) {
    const el = $('log');
    el.textContent = s.log.join('\n');
    el.scrollTop = el.scrollHeight;
  }
}
function setSYM(sym) { SYM = sym; loadChart(); loadState(); }
function setTF(tf) {
  TF = tf;
  document.querySelectorAll('.tfl').forEach(e => e.classList.toggle('on', e.dataset.tf === tf));
  document.querySelectorAll('.tf div[data-tf]').forEach(e => e.classList.toggle('on', e.dataset.tf === tf));
  loadChart();
}
async function act(what) {
  await fetch('/api/' + what, {method: 'POST'});
  setTimeout(loadState, 600);
}
async function tfChange(tf) {
  try {
    const d = await (await fetch('/api/candles?symbol=' + SYM + '&tf=' + tf)).json();
    const rows = d.rows; if (rows.length < 2) return null;
    return (rows[rows.length - 1].c - rows[0].o) / rows[0].o * 100;
  } catch (e) { return null; }
}
async function loadTfStrip() {
  for (const tf of ['5m', '1h', '1d']) {
    const ch = await tfChange(tf);
    const el = $('tf-' + tf);
    if (ch === null) { el.textContent = '–'; continue; }
    el.textContent = (ch >= 0 ? '+' : '') + ch.toFixed(1) + '%';
    el.className = ch >= 0 ? 'up' : 'dn';
  }
}
async function loadChart() {
  const data = await (await fetch('/api/candles?symbol=' + SYM + '&tf=' + TF)).json();
  const rows = data.rows; if (!rows.length) return;
  const last = rows[rows.length - 1];
  $('ct').textContent = SYM + '/USD · ' + TF + ' · Yahoo Finance';
  const chg = (last.c - rows[0].o) / rows[0].o * 100;
  $('ohlc').innerHTML = `<span>O ${last.o.toFixed(2)}</span><span>H ${last.h.toFixed(2)}</span><span>L ${last.l.toFixed(2)}</span><span>C ${last.c.toFixed(2)}</span><span class="${chg >= 0 ? 'up' : 'dn'}">${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%</span>`;
  $('volspan').textContent = last.v ? last.v.toLocaleString('en-US') : '–';
  const cv = $('c'), x = cv.getContext('2d');
  const r = cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  cv.width = r.width * dpr; cv.height = r.height * dpr;
  x.setTransform(dpr, 0, 0, dpr, 0, 0);
  const W = r.width, H = r.height, pr = 70, pb = 34, cw = W - pr, ch = H - pb;
  let hi = Math.max(...rows.map(d => d.h)), lo = Math.min(...rows.map(d => d.l));
  const pad = (hi - lo) * 0.07; hi += pad; lo -= pad;
  const Y = v => (hi - v) / (hi - lo) * ch;
  x.font = '12px Inter,sans-serif'; x.textAlign = 'left';
  x.strokeStyle = '#1a1c1f'; x.fillStyle = '#b4b7bc'; x.lineWidth = 1;
  const steps = Math.max(5, Math.floor(ch / 52));
  for (let i = 0; i <= steps; i++) {
    const p = lo + (hi - lo) * i / steps, y = Y(p);
    x.beginPath(); x.moveTo(0, y); x.lineTo(cw, y); x.stroke();
    x.fillText(p.toFixed(0), cw + 12, y + 4);
  }
  const bw = cw / rows.length, vh = ch * 0.16;
  const vmax = Math.max(...rows.map(d => d.v));
  rows.forEach((d, i) => {
    const px = i * bw + bw / 2, up = d.c >= d.o;
    x.fillStyle = up ? 'rgba(63,191,143,.5)' : 'rgba(229,83,75,.45)';
    const hgt = vmax ? d.v / vmax * vh : 0;
    x.fillRect(px - bw * 0.32, ch - hgt, Math.max(1, bw * 0.64), hgt);
    const col = up ? '#3fbf8f' : '#e5534b';
    x.strokeStyle = col; x.fillStyle = col;
    x.beginPath(); x.moveTo(px, Y(d.h)); x.lineTo(px, Y(d.l)); x.stroke();
    const t = Y(Math.max(d.o, d.c)), b = Y(Math.min(d.o, d.c));
    x.fillRect(px - bw * 0.32, t, Math.max(1, bw * 0.64), Math.max(1, b - t));
  });
  const ly = Y(last.c);
  x.setLineDash([2, 3]); x.strokeStyle = '#3fbf8f';
  x.beginPath(); x.moveTo(0, ly); x.lineTo(cw, ly); x.stroke(); x.setLineDash([]);
  x.fillStyle = '#3fbf8f'; x.fillRect(cw + 4, ly - 11, pr - 8, 22);
  x.fillStyle = '#fff'; x.font = '600 12px Inter'; x.fillText(last.c.toFixed(2), cw + 10, ly + 4);
  x.fillStyle = '#8b8e94'; x.font = '11px Inter'; x.textAlign = 'center';
  const every = Math.ceil(rows.length / 8);
  rows.forEach((d, i) => {
    if (i % every) return;
    const dt = new Date(d.t * 1000);
    const lbl = TF === '1d' ? dt.toLocaleDateString('en-GB', {day: '2-digit', month: 'short'})
      : dt.toLocaleTimeString('en-GB', {hour: '2-digit', minute: '2-digit'});
    x.fillText(lbl, i * bw + bw / 2, H - 10);
  });
}
setInterval(() => {
  const d = new Date(), f = n => String(n).padStart(2, '0');
  const off = -d.getTimezoneOffset() / 60;
  $('clk').textContent = `${f(d.getHours())}:${f(d.getMinutes())}:${f(d.getSeconds())} (UTC${off >= 0 ? '+' : ''}${off})  |  % log auto`;
}, 1000);
addEventListener('resize', loadChart);
loadState().then(() => { loadChart(); loadTfStrip(); });
setInterval(loadState, 3000);
setInterval(() => { loadChart(); loadTfStrip(); }, 60000);
</script>
</body>
</html>
"""


# -------------------------------------------------------------- handler
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path == "/":
                self._send(200, PAGE, "text/html; charset=utf-8")
            elif u.path == "/api/state":
                self._send(200, json.dumps(state_payload()))
            elif u.path == "/api/candles":
                q = parse_qs(u.query)
                sym = (q.get("symbol") or [SYMBOLS[0]])[0]
                tf = (q.get("tf") or ["5m"])[0]
                self._send(200, json.dumps(candles_payload(sym, tf)))
            elif u.path == "/logo.png":
                if os.path.exists(LOGO):
                    with open(LOGO, "rb") as f:
                        self._send(200, f.read(), "image/png")
                else:
                    self._send(200, base64.b64decode(LOGO_B64), "image/png")
            else:
                self._send(404, json.dumps({"error": "not found"}))
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}))

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/start":
            ok, msg = start_process(["learn"], "learn (forever)")
        elif u.path == "/api/backtest":
            ok, msg = start_process(["backtest"], "backtest")
        elif u.path == "/api/stop":
            ok, msg = stop_process()
        else:
            self._send(404, json.dumps({"error": "not found"}))
            return
        self._send(200, json.dumps({"ok": ok, "message": msg}))


def main():
    port = 8765
    open_browser = True
    args = sys.argv[1:]
    if "--no-open" in args:
        open_browser = False
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"Trading Agents GUI: {url}")
    print("Paper trading only. Ctrl+C stops the dashboard "
          "(a running learner started from the page keeps its own window rules — stop it from the page first).")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGUI closed.")


if __name__ == "__main__":
    main()
