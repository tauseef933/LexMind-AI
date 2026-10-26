"""
Synthetic evaluation corpus: a 5-page mutual NDA and a 4-page master
services agreement between overlapping parties.

Written for this repo (no third-party documents). Both contracts contain the
same kinds of clauses (confidentiality, liability cap, governing law,
disputes) with different values, so retrieval has to find the right
document as well as the right page.
"""

from pathlib import Path

import fitz  # PyMuPDF

NDA_PAGES = [
    # Page 1 — parties, purpose, effective date
    """MUTUAL NON-DISCLOSURE AGREEMENT

This Mutual Non-Disclosure Agreement (the "Agreement") is entered into on 14 March 2025
(the "Effective Date") by and between Northwind Analytics Ltd., a company incorporated in
England and Wales with its registered office at 12 Harbour Street, Bristol ("Northwind"), and
Quillon Robotics Inc., a Delaware corporation with its principal place of business at 800 Market
Avenue, Austin, Texas ("Quillon"). Northwind and Quillon are each a "Party".

Purpose. The Parties wish to evaluate a potential joint venture to develop warehouse inventory
drones (the "Purpose"). In connection with the Purpose, each Party may disclose information to
the other Party.""",
    # Page 2 — definition and exclusions
    """1. DEFINITION OF CONFIDENTIAL INFORMATION

"Confidential Information" means any non-public technical, financial or business information
disclosed by one Party (the "Discloser") to the other Party (the "Recipient"), including source
code, flight-control algorithms, supplier pricing, customer lists and product roadmaps, whether
disclosed orally, visually or in writing.

2. EXCLUSIONS

Confidential Information does not include information that: (a) is or becomes publicly available
through no fault of the Recipient; (b) was lawfully known to the Recipient before disclosure;
(c) is independently developed by the Recipient without use of the Discloser's information; or
(d) is rightfully received from a third party without a duty of confidentiality.""",
    # Page 3 — obligations and term
    """3. OBLIGATIONS OF THE RECIPIENT

The Recipient shall use Confidential Information solely for the Purpose, shall protect it with at
least the same degree of care it uses for its own confidential information and no less than
reasonable care, and shall disclose it only to employees and advisers who need to know it for the
Purpose and who are bound by written confidentiality duties at least as protective as these.

4. TERM

This Agreement remains in force for two (2) years from the Effective Date. The confidentiality
obligations survive expiry or termination of this Agreement for a period of five (5) years, except
for trade secrets, which shall be protected for as long as they remain trade secrets under
applicable law.""",
    # Page 4 — return of materials, remedies, no licence
    """5. RETURN OR DESTRUCTION OF MATERIALS

Within thirty (30) days after a written request from the Discloser, the Recipient shall return or
destroy all documents and copies containing Confidential Information and confirm this in writing,
signed by an officer of the Recipient.

6. REMEDIES

Each Party acknowledges that a breach may cause irreparable harm for which damages would not be an
adequate remedy. The Discloser shall therefore be entitled to seek injunctive relief and specific
performance, in addition to any other remedies available at law. Neither Party's total liability
under this Agreement shall exceed five hundred thousand US dollars (USD 500,000).

7. NO LICENCE

Nothing in this Agreement grants any licence under any patent, copyright or other intellectual
property right of the Discloser.""",
    # Page 5 — governing law, disputes, notices, signatures
    """8. GOVERNING LAW AND DISPUTES

This Agreement is governed by the laws of the State of New York. Any dispute shall be finally
resolved by arbitration administered by the International Centre for Dispute Resolution, seated in
New York City, before a single arbitrator.

9. NOTICES

Notices must be in writing and sent by courier or email to the addresses set out above, marked for
the attention of the General Counsel of the receiving Party.

Signed for Northwind Analytics Ltd. by Helena Marsh, Chief Executive Officer.
Signed for Quillon Robotics Inc. by David Okafor, Chief Operating Officer.""",
]

MSA_PAGES = [
    # Page 1 — parties, services, fees
    """MASTER SERVICES AGREEMENT

This Master Services Agreement is made on 2 June 2025 between Northwind Analytics Ltd.
("Customer") and Harbor Freight Logistics LLC, a California limited liability company
("Provider").

1. SERVICES. Provider shall supply cold-chain warehousing and last-mile delivery services as
described in each statement of work signed by both parties.

2. FEES. Customer shall pay a monthly fee of forty-two thousand US dollars (USD 42,000), invoiced
on the first business day of each month and payable within forty-five (45) days of invoice.
Late payments accrue interest at 1.5% per month.""",
    # Page 2 — service levels and confidentiality
    """3. SERVICE LEVELS. Provider shall achieve on-time delivery of at least 98.5% of shipments each
calendar month. For each full percentage point below that target, Customer receives a service
credit equal to 4% of that month's fee, capped at 20% of the monthly fee.

4. CONFIDENTIALITY. Each party shall keep the other's business information confidential during
the term of this Agreement and for three (3) years after it ends. Shipment data and route plans
are Customer's confidential information.""",
    # Page 3 — term, termination, liability
    """5. TERM AND TERMINATION. This Agreement runs for an initial term of three (3) years and renews
automatically for successive one-year periods. Either party may terminate for convenience by
giving sixty (60) days' written notice. Either party may terminate immediately if the other
commits a material breach not cured within fifteen (15) days of notice.

6. LIMITATION OF LIABILITY. Each party's aggregate liability under this Agreement is limited to
two million US dollars (USD 2,000,000). Neither party is liable for lost profits or other
indirect damages.""",
    # Page 4 — insurance, governing law, signatures
    """7. INSURANCE. Provider shall maintain cargo insurance of at least USD 5,000,000 per occurrence
and name Customer as an additional insured.

8. GOVERNING LAW. This Agreement is governed by the laws of the State of California. The state and
federal courts located in San Francisco County have exclusive jurisdiction over any dispute.

Signed for Northwind Analytics Ltd. by Helena Marsh, Chief Executive Officer.
Signed for Harbor Freight Logistics LLC by Priya Raman, Managing Member.""",
]

DOCUMENTS = {
    "Northwind-Quillon-NDA.pdf": NDA_PAGES,
    "Northwind-Harbor-MSA.pdf": MSA_PAGES,
}


def build_pdf(path: Path, pages: list[str]) -> Path:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()  # A4
        page.insert_textbox(page.rect + (60, 60, -60, -60), text, fontsize=10.5, fontname="helv")
    doc.save(path)
    return path
