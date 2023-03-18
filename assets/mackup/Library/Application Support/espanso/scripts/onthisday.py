import datetime


def suffix(d: int) -> str:
    if 11 <= d <= 13:
        return "th"
    elif d % 10 == 1:
        return "st"
    elif d % 10 == 2:
        return "nd"
    elif d % 10 == 3:
        return "rd"
    else:
        return "th"


def custom_strftime(format: str, t: datetime.datetime) -> str:
    return t.strftime(format).replace("{S}", str(t.day) + suffix(t.day))


dates = ["[[历史上的今天]]"]

for i in range(3):
    date = datetime.datetime.now() - datetime.timedelta(days=(365 * (i + 1)))
    dates.append("[[" + custom_strftime("%B {S}, %Y", date) + "]]")

# output = "\n  ".join(dates)

output = dates[0] + "：" + dates[1] + "、" + dates[2] + "、" + dates[3]

print(output)
