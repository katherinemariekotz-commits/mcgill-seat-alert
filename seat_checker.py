import os
import re
import smtplib
from email.message import EmailMessage

import requests
from bs4 import BeautifulSoup


TERM = "202609"

COURSES = {
    "SOCI 213": "5706",
    "PSYC 213": "5555",
}


def get_remaining_seats(crn):
    url = (
        "https://horizon.mcgill.ca/pban1/"
        "bwckschd.p_disp_detail_sched"
        f"?term_in={TERM}&crn_in={crn}"
    )

    response = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text(" ", strip=True)

    # Look for the Registration Availability table.
    match = re.search(
        r"Seats\s+Capacity\s+Actual\s+Remaining\s+(\d+)\s+(\d+)\s+(\d+)",
        text,
        re.IGNORECASE,
    )

    if not match:
        raise RuntimeError(
            f"Couldn't read seat availability for CRN {crn}."
        )

    capacity = int(match.group(1))
    actual = int(match.group(2))
    remaining = int(match.group(3))

    return capacity, actual, remaining


def send_email(open_courses):
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]
    notification_email = os.environ["NOTIFICATION_EMAIL"]

    msg = EmailMessage()
    msg["Subject"] = "🚨 McGill class seat OPEN"
    msg["From"] = gmail_address
    msg["To"] = notification_email

    lines = [
        "GO TO MINERVA — a seat appears to be available:",
        ""
    ]

    for course, crn, remaining in open_courses:
        lines.append(
            f"{course} — CRN {crn} — {remaining} seat(s) remaining"
        )

    lines += [
        "",
        "Register as soon as possible because the seat may disappear quickly."
    ]

    msg.set_content("\n".join(lines))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(gmail_address, gmail_app_password)
        smtp.send_message(msg)


def main():
    open_courses = []

    for course, crn in COURSES.items():
        capacity, actual, remaining = get_remaining_seats(crn)

        print(
            f"{course} ({crn}): "
            f"{actual}/{capacity} enrolled — "
            f"{remaining} remaining"
        )

        if remaining > 0:
            open_courses.append((course, crn, remaining))

    if open_courses:
        send_email(open_courses)
        print("ALERT SENT")
    else:
        print("No seats available.")


if __name__ == "__main__":
    main()
