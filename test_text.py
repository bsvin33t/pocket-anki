# Run on the Mac: python3 test_text.py
from text import back_side, center, strip_html, wrap

html = '<style>.card{color:red}</style>front<hr id=answer>The <b>cat</b>&nbsp;sat<br>on &amp; off[sound:a.mp3][anki:play:q:0]'
assert strip_html(back_side(html)) == "The cat sat\non & off"
assert strip_html("<div>a</div><div>b</div>") == "a\nb"
assert wrap("aa bb cc", 5) == ["aa bb", "cc"]
assert wrap("abcdefgh", 3) == ["abc", "def", "gh"]
assert wrap("x\ny", 10) == ["x", "y"]
assert center(["ab", "abcd"], 6, 5) == ["", "  ab", " abcd"]
assert center(["x"] * 9, 6, 5)[0] == "  x"  # overfull: no top padding
assert strip_html("to imagine\n[[type:Front]]") == "to imagine"
print("ok")
