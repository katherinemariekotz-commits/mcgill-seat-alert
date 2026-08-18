import os
import smtplib
from email.message import EmailMessage

from playwright.sync_api import sync_playwright


VSB_URL = """https://vsb.mcgill.ca/criteria.jsp?access=0&lang=en&tip=2&page=criteria&scratch=0&advice=0&legend=1&term=202609&sort=none&filters=iiiiiiiiii&bbs=&ds=&cams=DOWNTOWN_MACDONALD_OFF-CAMPUS_DISTANCE&locs=any&isrts=any&ses=any&pl=&pac=1&course_0_0=SOCI-213&va_0_0=1674&sa_0_0=&cs_0_0=--202609_5706--&cpn_0_0=&csn_0_0=&ca_0_0=&dropdown_0_0=al&ig_0_0=0&rq_0_0=&bg_0_0=0&cr_0_0=&ss_0_0=0&sbc_0_0=0&course_1_0=PSYC-213&va_1_0=0628&sa_1_0=&cs_1_0=--202609_5555--&cpn_1_0=&csn_1_0=&ca_1_0=&dropdown_1_0=al&ig_1_0=0&rq_1_0=&bg_1_0=0&cr_1_0=&ss_1_0=0&sbc_1_0=0"""

COURSES = {
    "SOCI 213": "5706",
    "PSYC 213": "5555",
}


def get_course_status(page, course, crn):
    block = page.evaluate(
        """
        ({course, crn}) => {
            const variants = [
                course,
                course.replace(" ", "-"),
                crn
            ];

            const elements = [...document.querySelectorAll("body *")];

            const matches = elements.filter(el => {
                const txt = (el.innerText || "").replace(/\\s+/g, " ").trim();
                return variants.some(v => txt.includes(v));
            });

            // Start with the smallest matching elements.
            matches.sort(
                (a, b) =>
                    (a.innerText || "").length -
                    (b.innerText || "").length
            );

            for (const match of matches) {
                let el = match;

                // Walk upward until we find the course card/container.
                for (let i = 0; i < 10 && el; i++) {
                    const txt = (el.innerText || "")
                        .replace(/\\s+/g, " ")
                        .trim();

                    const identifiesCourse =
                        txt.includes(course) ||
                        txt.includes(course.replace(" ", "-")) ||
                        txt.includes(crn);

                    if (
                        identifiesCourse &&
                        txt.length > 20 &&
                        txt.length < 4000
                    ) {
                        if (
                            txt.includes("All classes are full") ||
                            txt.toLowerCase().includes("seats") ||
                            txt.toLowerCase().includes("waitlist")
                        ) {
                            return txt;
                        }
                    }

                    el = el.parentElement;
                }
            }

            return null;
        }
        """,
        {"course": course, "crn": crn},
    )

    if block is None:
        return "UNKNOWN", ""

    print(f"\\n--- {course} BLOCK ---")
    print(block)
    print("----------------------\\n")

    if "all classes are full" in block.lower():
        return "FULL", block

    # VSB normally displays "All classes are full" when the locked
    # section cannot be enrolled in. If that warning disappears,
    # we treat it as a possible opening and alert immediately.
    return "POSSIBLY_OPEN", block


def send_email(open_courses):
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]
    notification_email = os.environ["NOTIFICATION_EMAIL"]

    msg = EmailMessage()

    names = ", ".join(course for course, _ in open_courses)

    msg["Subject"] = f"🚨 MCGILL SEAT MAY BE OPEN: {names}"
    msg["From"] = gmail_address
    msg["To"] = notification_email

    lines = [
        "CHECK MINERVA NOW.",
        "",
        "VSB is no longer reporting the following section as full:",
        "",
    ]

    for course, crn in open_courses:
        lines.append(f"🚨 {course} — CRN {crn}")

    lines.extend(
        [
            "",
            "Go to Minerva immediately and try to register.",
            "",
            "This notifier does not register you automatically.",
        ]
    )

    msg.set_content("\\n".join(lines))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(gmail_address, gmail_app_password)
        smtp.send_message(msg)

    print("EMAIL ALERT SENT")


def main():
    open_courses = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        print("Opening McGill VSB...")

        page.goto(
            VSB_URL,
            wait_until="domcontentloaded",
            timeout=90000,
        )

        # Give VSB's JavaScript time to populate the course information.
        page.wait_for_timeout(10000)

        print("VSB loaded.")

        for course, crn in COURSES.items():
            status, block = get_course_status(page, course, crn)

            print(f"{course} (CRN {crn}): {status}")

            if status == "POSSIBLY_OPEN":
                open_courses.append((course, crn))

        browser.close()

    if open_courses:
        send_email(open_courses)
    else:
        print("Both monitored sections are still full.")


if __name__ == "__main__":
    main()
