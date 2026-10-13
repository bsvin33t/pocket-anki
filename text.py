# Plain-text helpers shared by code.py (device) and test_text.py (Mac).
import re

ENTITIES = (("&nbsp;", " "), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"), ("&amp;", "&"))


def strip_html(html):
    # ponytail: drops <style> blocks by hand because MicroPython re has no DOTALL
    while "<style" in html:
        a = html.find("<style")
        b = html.find("</style>", a)
        html = html[:a] + (html[b + 8:] if b >= 0 else "")
    html = re.sub(r"<br ?/?>|</div>|</p>|</li>", "\n", html)
    html = re.sub(r"<[^>]*>", "", html)
    html = re.sub(r"\[(sound|anki:play):[^\]]*\]|\[\[type:[^\]]*\]\]", "", html)
    for e, c in ENTITIES:
        html = html.replace(e, c)
    lines = [" ".join(l.split()) for l in html.split("\n")]
    return "\n".join(l for l in lines if l)


def back_side(answer_html):
    # Anki renders the back as: front + <hr id=answer> + back
    i = answer_html.find("id=answer>")
    return answer_html[i + 10:] if i >= 0 else answer_html


def center(lines, cols, rows):
    top = [""] * ((rows - len(lines)) // 2)
    return top + [" " * ((cols - len(l)) // 2) + l for l in lines]


def wrap(text, cols):
    out = []
    for para in text.split("\n"):
        line = ""
        for w in para.split(" "):
            while len(w) > cols:  # hard-split words longer than a line
                if line:
                    out.append(line)
                    line = ""
                out.append(w[:cols])
                w = w[cols:]
            if not line:
                line = w
            elif len(line) + 1 + len(w) <= cols:
                line += " " + w
            else:
                out.append(line)
                line = w
        out.append(line)
    return out
