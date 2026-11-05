import sys, os
OUT = sys.argv[1]
CYAN, INK, WHITE = "#00E5D2", "#0E0D10", "#F4F4F6"

def stick(x, y, w, h, a, b, uid):
    # rounded stick filled with colour a, diagonal stripes in colour b
    step, sw, slant = 150, 75, 56
    polys = []
    sx = x - slant - step
    while sx < x + w + step:
        polys.append(f'<polygon points="{sx+slant},{y} {sx+slant+sw},{y} {sx+sw},{y+h} {sx},{y+h}"/>')
        sx += step
    return (f'<clipPath id="c{uid}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14"/></clipPath>'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{a}"/>'
            f'<g clip-path="url(#c{uid})" fill="{b}">{"".join(polys)}</g>')

def mark(board_fill, board_line, stick_a, stick_b, detail, outline=None, y1=540, y2=700):
    X, W = 192, 640
    s = []
    # top (open) clapper, hinged at left
    s.append(f'<g transform="rotate(-17 {X} 342)">{stick(X, 266, W, 76, stick_a, stick_b, "t")}</g>')
    s.append(stick(X, 344, W, 76, stick_a, stick_b, "b"))
    # board
    st = f' stroke="{outline}" stroke-width="28"' if outline else ''
    s.append(f'<rect x="{X}" y="440" width="{W}" height="400" rx="40" fill="{board_fill}"{st}/>')
    # simplified slate info: one rule + ROLL|SCENE|TAKE row
    lw = 18
    s.append(f'<g stroke="{detail}" stroke-width="{lw}" stroke-linecap="round">'
             f'<line x1="{X+64}" y1="{y1}" x2="{X+W-64}" y2="{y1}"/>'
             f'<line x1="{X+64}" y1="{y2}" x2="{X+W-64}" y2="{y2}"/>'
             f'<line x1="{X+W/3}" y1="{y1}" x2="{X+W/3}" y2="{y2}"/>'
             f'<line x1="{X+2*W/3}" y1="{y1}" x2="{X+2*W/3}" y2="{y2}"/></g>')
    return "".join(s)

def svg(body, bg=None):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="1024" height="1024">{bg or ""}{body}</svg>'

def icon_bg():
    return (f'<rect x="40" y="40" width="944" height="944" rx="210" fill="{INK}" stroke="{CYAN}" stroke-width="36"/>')

def shift(body, dy=10, scale=0.88):
    c = 512
    return f'<g transform="translate({c} {c+dy}) scale({scale}) translate({-c} {-c})">{body}</g>'

V = {
 # A: white board, cyan/ink stripes  (closest to the reference photo)
 "A": mark(WHITE, INK, CYAN, INK, INK),
 # B: dark board w/ cyan outline + cyan rules, cyan/white stripes
 "B": mark(INK, CYAN, CYAN, WHITE, CYAN, outline=CYAN),
 # C: cyan board, ink rules, white/ink stripes
 "C": mark(CYAN, INK, WHITE, INK, INK),
 # D: white board (A) + white/ink stripes (C), rules centred in the board (440..840 -> 560/720)
 "D": mark(WHITE, INK, WHITE, INK, INK, y1=560, y2=720),
}
for k, body in V.items():
    open(f"{OUT}/slate-{k}-icon.svg","w").write(svg(shift(body), icon_bg()))
    open(f"{OUT}/slate-{k}-mark.svg","w").write(svg(body))
