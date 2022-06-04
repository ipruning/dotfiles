from datetime import datetime as dt


def suffix(d):
    return "th" if 11 <= d <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d % 10, "th")


def custom_strftime(format, t):
    return t.strftime(format).replace("{S}", str(t.day) + suffix(t.day))


output = (
    "[["
    + custom_strftime("%B {S}, %Y", dt.now())
    + "]]"
    + " "
    + custom_strftime("%H:%M", dt.now())
)

print(output)
