"""
Builds data/name_pairs.csv: 148 hand-labeled name pairs.

How and why this was constructed
---------------------------------
Every pair below was written by hand (not scraped or auto-generated) to target
a specific, named failure mode in Indian KYC name matching. The exercise brief
calls out several categories explicitly; this dataset covers each of them with
multiple examples, PLUS three "hard negative" categories designed to catch
matchers that are too permissive:

  IDENTICAL        - trivial positives (case/whitespace/punctuation noise only)
  INITIALS         - "S. Kumar" vs "Suresh Kumar"
  ORDER            - surname-first vs given-name-first, seen on some state ID
                      formats and bank KYC forms
  TRANSLIT         - Mohammed/Mohammad/Muhammad-style spelling variants of the
                      same underlying name
  MIDDLE           - missing/abbreviated middle names, and S/O, D/O, W/O
                      (son/daughter/wife-of) father's/husband's-name conventions
  HONORIFIC        - Shri, Smt., Kumari, Jr., Sr., Dr., Mr./Mrs., Bhai/Ben
  TYPO             - small single-character OCR/typing errors
  EASY_NEG         - obviously different people (sanity-check negatives)
  SIBLING          - hardest negative class: same surname AND same father's/
                      husband's name, different given name (real siblings or
                      spouses commonly produce exactly this on ID documents)
  COMMON_SURNAME   - different given names sharing a common Indian surname
  NEAR_DUP         - different people whose names are one edit or one phoneme
                      away from each other (deliberately adversarial: designed
                      to fool a matcher that's tuned to be too lenient)
  HONORIFIC_NEG    - honorific present, but the underlying names still differ
                      (checks that honorific-stripping doesn't itself create a
                      false match)
  PREFIX_ABBREV    - "Md"/"Mohd" as an abbreviation for "Mohammed" as a name
                      PREFIX (common in South Asian Muslim names), not to be
                      confused with the "Doctor of Medicine" reading
  TRUNCATED        - older ID systems (Aadhaar, some bank forms) cut long
                      names off at a fixed field length, mid-word
  SEGMENTATION     - the same compound name split into a different number of
                      words across documents (one fused word vs several
                      separate words). Real examples contributed and verified
                      by the user against their own family's names.

Two related failure modes came up during review but are deliberately left
OUT of this dataset because they cannot be solved by name matching at all,
and the exercise is explicitly scoped to name-string comparison, not full
identity verification:
  - two genuinely different people who share the exact same legal name
    (the strings are identical -- there is nothing left to compare)
  - single-token, highly generic names ("Kumar" alone) carrying very low
    identifying signal on their own
Both are noted as limitations in NOTES.md rather than "solved" here.

The positive/negative split is roughly 82/46 (~64% positive), which is
intentionally not 50/50: real KYC matching traffic is dominated by genuine
same-person pairs with formatting noise, but the negative set is deliberately
weighted toward hard cases (SIBLING, COMMON_SURNAME, NEAR_DUP) rather than easy
ones, because that's where a shipping decision actually gets made.
"""
import csv
import os

# (name_a, name_b, label, category, note)
# label: "match" or "non_match"
PAIRS = [
    # ---- IDENTICAL (trivial positives) ----
    ("Suresh Kumar", "Suresh Kumar", "match", "IDENTICAL", "exact duplicate"),
    ("Priya Sharma", "priya sharma", "match", "IDENTICAL", "case only"),
    ("Anjali Verma", "Anjali  Verma", "match", "IDENTICAL", "extra whitespace"),
    ("Rajesh Gupta", "Rajesh, Gupta", "match", "IDENTICAL", "comma noise"),
    ("Meena Nair", "MEENA NAIR", "match", "IDENTICAL", "all caps"),
    ("Vikram Singh", "Vikram Singh.", "match", "IDENTICAL", "trailing period"),
    ("Deepak Rao", "Deepak Rao ", "match", "IDENTICAL", "trailing space"),
    ("Sunita Joshi", "Sunita Joshi", "match", "IDENTICAL", "control duplicate"),

    # ---- INITIALS vs expanded ----
    ("S. Kumar", "Suresh Kumar", "match", "INITIALS", ""),
    ("R. Sharma", "Rakesh Sharma", "match", "INITIALS", ""),
    ("A. K. Verma", "Anil Kumar Verma", "match", "INITIALS", "both given names initialed"),
    ("P. Reddy", "Padma Reddy", "match", "INITIALS", ""),
    ("M. Iyer", "Meera Iyer", "match", "INITIALS", ""),
    ("V. Singh", "Vikas Singh", "match", "INITIALS", ""),
    ("K. Nair", "Kavya Nair", "match", "INITIALS", ""),
    ("Suresh K.", "Suresh Kumar", "match", "INITIALS", "surname initialed instead"),
    ("D. Patel", "Dinesh Patel", "match", "INITIALS", ""),
    ("N. Rao", "Nirmala Rao", "match", "INITIALS", ""),
    ("J. Mehta", "Jayesh Mehta", "match", "INITIALS", ""),
    ("S.K. Gupta", "Sunil Kumar Gupta", "match", "INITIALS", "both middle+given initialed"),
    ("A. Reddy", "Anitha Reddy", "match", "INITIALS", ""),
    ("R.K. Singh", "Ramesh Kumar Singh", "match", "INITIALS", ""),

    # ---- ORDER: surname-first vs given-first ----
    ("Sharma Rakesh", "Rakesh Sharma", "match", "ORDER", ""),
    ("Reddy Padma", "Padma Reddy", "match", "ORDER", ""),
    ("Nair Meera", "Meera Nair", "match", "ORDER", ""),
    ("Verma Anil Kumar", "Anil Kumar Verma", "match", "ORDER", "3-token reorder"),
    ("Singh Vikas", "Vikas Singh", "match", "ORDER", ""),
    ("Iyer Krishnan", "Krishnan Iyer", "match", "ORDER", ""),
    ("Gupta Sunil", "Sunil Gupta", "match", "ORDER", ""),
    ("Rao Nirmala", "Nirmala Rao", "match", "ORDER", ""),
    ("Patel Dinesh", "Dinesh Patel", "match", "ORDER", ""),
    ("Joshi Sunita", "Sunita Joshi", "match", "ORDER", ""),
    ("Mehta Jayesh", "Jayesh Mehta", "match", "ORDER", ""),
    ("Kumar Suresh", "Suresh Kumar", "match", "ORDER", ""),

    # ---- TRANSLITERATION variants ----
    ("Mohammed Farooq", "Mohammad Farooq", "match", "TRANSLIT", ""),
    ("Mohammed Farooq", "Muhammad Farooq", "match", "TRANSLIT", ""),
    ("Mohammad Yusuf", "Muhammad Yousuf", "match", "TRANSLIT", ""),
    ("Lakshmi Devi", "Laxmi Devi", "match", "TRANSLIT", ""),
    ("Shiva Kumar", "Siva Kumar", "match", "TRANSLIT", ""),
    ("Krishnan Nair", "Krishnann Nair", "match", "TRANSLIT", "doubled consonant"),
    ("Sunita Kumari", "Suneeta Kumari", "match", "TRANSLIT", ""),
    ("Zakir Hussain", "Zakir Hussein", "match", "TRANSLIT", ""),
    ("Aisha Begum", "Ayesha Begum", "match", "TRANSLIT", ""),
    ("Farhan Sheikh", "Farhaan Shaikh", "match", "TRANSLIT", "both tokens vary"),
    ("Rukmini Devi", "Rukmani Devi", "match", "TRANSLIT", ""),
    ("Chandran Pillai", "Chandran Pillay", "match", "TRANSLIT", ""),
    ("Yasmin Sultana", "Yasmeen Sultana", "match", "TRANSLIT", ""),
    ("Abdul Kareem", "Abdul Karim", "match", "TRANSLIT", ""),
    ("Kondapalli", "Kondapally", "match", "TRANSLIT", "user-contributed: surname spelling variant, same pronunciation"),
    ("Vidya Balan", "Vidhya Balan", "match", "TRANSLIT", "corrected: user flagged this as a real spelling variant, not two different people -- originally mislabeled as NEAR_DUP"),
    ("Naveen Reddy", "Naveen Reddi", "match", "TRANSLIT", "corrected: Reddy/Reddi are both legitimate spellings of the same surname -- originally mislabeled as NEAR_DUP"),

    # ---- MIDDLE / father's / husband's name conventions ----
    ("Anil Kumar Sharma", "Anil Sharma", "match", "MIDDLE", "middle name dropped"),
    ("Ramesh S/O Krishna Murthy", "Ramesh Krishna Murthy", "match", "MIDDLE", "S/O particle only"),
    ("Priya Reddy", "Priya Venkat Reddy", "match", "MIDDLE", "husband's first name inserted post-marriage"),
    ("Kavita W/O Suresh Patel", "Kavita Suresh Patel", "match", "MIDDLE", "W/O particle only"),
    ("Neha D/O Ramesh Gupta", "Neha Gupta", "match", "MIDDLE", "D/O + father's name dropped"),
    ("Anita Devi", "Anita Kumari Devi", "match", "MIDDLE", "middle name added"),
    ("Vijay Kumar Yadav", "Vijay Yadav", "match", "MIDDLE", "middle name dropped"),
    ("Ramesh Chandra Pandey", "Ramesh Pandey", "match", "MIDDLE", "middle name dropped"),
    ("Sunil S/O Late Prakash Joshi", "Sunil Prakash Joshi", "match", "MIDDLE", "S/O + Late both stripped"),
    ("Meera Ben Patel", "Meera Patel", "match", "MIDDLE", "Gujarati 'Ben' suffix"),
    ("Rajesh Bhai Shah", "Rajesh Shah", "match", "MIDDLE", "Gujarati 'Bhai' suffix"),
    ("Kamala W/O Late Ramaiah", "Kamala Ramaiah", "match", "MIDDLE", "W/O + Late both stripped"),
    ("Geeta D/O Mohan Kumari", "Geeta Kumari", "match", "MIDDLE", "D/O + father's name dropped"),
    ("Suman Lata Mishra", "Suman Mishra", "match", "MIDDLE", "middle name dropped"),

    # ---- HONORIFICS and suffixes ----
    ("Shri Ramesh Kumar", "Ramesh Kumar", "match", "HONORIFIC", ""),
    ("Smt. Sunita Devi", "Sunita Devi", "match", "HONORIFIC", ""),
    ("Kumari Anjali Sharma", "Anjali Sharma", "match", "HONORIFIC", ""),
    ("Dr. Vikram Singh", "Vikram Singh", "match", "HONORIFIC", ""),
    ("Mr. Suresh Gupta", "Suresh Gupta", "match", "HONORIFIC", ""),
    ("Mrs. Padma Reddy", "Padma Reddy", "match", "HONORIFIC", ""),
    ("Prof. Anil Verma", "Anil Verma", "match", "HONORIFIC", ""),
    ("Late Shri Mohan Lal", "Mohan Lal", "match", "HONORIFIC", "two honorifics stacked"),
    ("Vikas Singh Jr.", "Vikas Singh", "match", "HONORIFIC", "suffix"),
    ("Ramesh Iyer Sr.", "Ramesh Iyer", "match", "HONORIFIC", "suffix"),

    # ---- TYPOS / OCR-style noise ----
    ("Sushma Reddy", "Sushama Reddy", "match", "TYPO", ""),
    ("Abhishek Mishra", "Abheshek Mishra", "match", "TYPO", ""),
    ("Rajendra Prasad", "Rajender Prasad", "match", "TYPO", ""),
    ("Kiran Bedi", "Kirn Bedi", "match", "TYPO", "dropped vowel"),
    ("Deepika Kaur", "Deepica Kaur", "match", "TYPO", ""),
    ("Manoj Tiwari", "Manoj Tiwary", "match", "TYPO", ""),
    ("Vishal Chaudhary", "Vishal Choudhary", "match", "TYPO", ""),
    ("Nikhil Bansal", "Nikhal Bansal", "match", "TYPO", ""),
    ("Pooja Malhotra", "Puja Malhotra", "match", "TYPO", ""),
    ("Harish Chandra", "Harish Chander", "match", "TYPO", ""),
    ("Farhan Akhtar", "Farhan Akthar", "match", "TYPO", "corrected: letter transposition, not a different person -- originally mislabeled as NEAR_DUP"),

    # ---- EASY negatives (sanity check) ----
    ("Suresh Kumar", "Anita Desai", "non_match", "EASY_NEG", ""),
    ("Ramesh Gupta", "Farhan Sheikh", "non_match", "EASY_NEG", ""),
    ("Priya Sharma", "Vikas Yadav", "non_match", "EASY_NEG", ""),
    ("Mohammed Ali", "John Fernandes", "non_match", "EASY_NEG", ""),
    ("Lakshmi Devi", "Rajesh Iyer", "non_match", "EASY_NEG", ""),
    ("Kavya Nair", "Sunil Bhatt", "non_match", "EASY_NEG", ""),
    ("Ananya Roy", "Deepak Chopra", "non_match", "EASY_NEG", ""),
    ("Rekha Menon", "Arvind Pillai", "non_match", "EASY_NEG", ""),
    ("Sonal Shah", "Kunal Mehta", "non_match", "EASY_NEG", ""),
    ("Neeraj Pandey", "Shalini Kapoor", "non_match", "EASY_NEG", ""),

    # ---- SIBLING (hardest negative: shared surname + father's/husband's name) ----
    ("Rohan S/O Manoj Sharma", "Rohit S/O Manoj Sharma", "non_match", "SIBLING", "brothers"),
    ("Ananya D/O Ravi Kumar", "Aparna D/O Ravi Kumar", "non_match", "SIBLING", "sisters"),
    ("Vikram Malhotra", "Vikas Malhotra", "non_match", "SIBLING", "brothers, no father's name given"),
    ("Priyanka Reddy", "Priyamvada Reddy", "non_match", "SIBLING", "sisters, near-identical given name"),
    ("Suresh Kumar Patel", "Umesh Kumar Patel", "non_match", "SIBLING", "shared middle+surname"),
    ("Kiran S/O Ramesh Nair", "Kishore S/O Ramesh Nair", "non_match", "SIBLING", "brothers"),
    ("Deepa W/O Manoj Gupta", "Deepika W/O Manoj Gupta", "non_match", "SIBLING", "two wives/relatives, same husband's name"),
    ("Anil Kumar Yadav", "Sunil Kumar Yadav", "non_match", "SIBLING", "brothers"),
    ("Neha Sharma", "Nisha Sharma", "non_match", "SIBLING", "sisters"),
    ("Arjun Reddy", "Arun Reddy", "non_match", "SIBLING", "brothers"),

    # ---- COMMON_SURNAME (different given names, shared common surname) ----
    ("Rajesh Kumar", "Ramesh Kumar", "non_match", "COMMON_SURNAME", ""),
    ("Suman Sharma", "Seema Sharma", "non_match", "COMMON_SURNAME", ""),
    ("Vinod Gupta", "Vinay Gupta", "non_match", "COMMON_SURNAME", ""),
    ("Kavita Reddy", "Kavya Reddy", "non_match", "COMMON_SURNAME", ""),
    ("Manish Patel", "Manoj Patel", "non_match", "COMMON_SURNAME", ""),
    ("Asha Nair", "Usha Nair", "non_match", "COMMON_SURNAME", ""),
    ("Sandeep Singh", "Sandesh Singh", "non_match", "COMMON_SURNAME", ""),
    ("Rohit Verma", "Rohan Verma", "non_match", "COMMON_SURNAME", ""),
    ("Geeta Joshi", "Geeta Mishra", "non_match", "COMMON_SURNAME", "same given name, different surname"),
    ("Arvind Kumar", "Anand Kumar", "non_match", "COMMON_SURNAME", ""),

    # ---- NEAR_DUP (adversarial: one edit / one phoneme from each other) ----
    ("Amit Singh", "Sumit Singh", "non_match", "NEAR_DUP", ""),
    ("Kavita Rao", "Kavya Rao", "non_match", "NEAR_DUP", ""),
    ("Sana Khan", "Saina Khan", "non_match", "NEAR_DUP", ""),
    ("Rahul Dev", "Rahul Dave", "non_match", "NEAR_DUP", "different surname, near-identical spelling"),
    ("Meenal Joshi", "Meena Joshi", "non_match", "NEAR_DUP", "Meenal and Meena are distinct registered given names, not spelling variants of each other"),
    ("Aditi Rao", "Aditya Rao", "non_match", "NEAR_DUP", "different given name, high char overlap"),
    ("Ishaan Kapoor", "Ishwar Kapoor", "non_match", "NEAR_DUP", ""),
    ("Karan Oberoi", "Kiran Oberoi", "non_match", "NEAR_DUP", "Karan and Kiran are distinct established given names"),
    ("Sonal Verma", "Sonam Verma", "non_match", "NEAR_DUP", "Sonal and Sonam are distinct established given names"),
    ("Nikita Malhotra", "Nikhat Malhotra", "non_match", "NEAR_DUP", "Nikita and Nikhat are distinct established given names"),

    # ---- PREFIX_ABBREV: "Md"/"Mohd" as an abbreviation for "Mohammed" ----
    # (not "Doctor of Medicine" -- far more common as a name prefix on South
    # Asian Muslim identity documents than as a professional suffix)
    ("Md. Rafiqul Islam", "Mohammed Rafiqul Islam", "match", "PREFIX_ABBREV", ""),
    ("Mohd Aslam Khan", "Mohammed Aslam Khan", "match", "PREFIX_ABBREV", ""),
    ("Md Imran Ansari", "Muhammad Imran Ansari", "match", "PREFIX_ABBREV", "abbrev + translit variant together"),
    ("Mohd. Shakeel Ahmed", "Mohammad Shakeel Ahmed", "match", "PREFIX_ABBREV", ""),
    ("Md. Aziz Rahman", "Md. Aziz Rehman", "match", "PREFIX_ABBREV", "both abbreviated, minor spelling drift"),
    ("Md Farhan Alam", "Rehan Alam", "non_match", "PREFIX_ABBREV", "different given name behind the abbreviation -- hard negative"),

    # ---- TRUNCATED: older ID systems cut long names at a fixed field length ----
    ("Seethamahalakshmi Devi", "SEETHAMAHALAKSHM", "match", "TRUNCATED", "Aadhaar-style field truncation mid-word"),
    ("Venkata Subramanyam Naidu", "VENKATA SUBRAMANYAM N", "match", "TRUNCATED", "truncated at last name"),
    ("Chandrasekhara Rao Yerramsetti", "CHANDRASEKHARA RAO YER", "match", "TRUNCATED", "long surname cut off"),
    ("Ramalingeswara Rao", "RAMALINGESWARA R", "match", "TRUNCATED", ""),
    ("Suresh Kumar", "SURES", "non_match", "TRUNCATED", "truncated too aggressively to be trustworthy -- too little signal left, hard negative by design"),

    # ---- SEGMENTATION: same compound name, split into a different number of
    # words across documents. Real examples, contributed and verified by the
    # user against their own family names. ----
    ("Seethamahalakshmi", "Seeta maha laxmi", "match", "SEGMENTATION", "user-contributed: mother's name, 1 word vs 3 words + spelling variant"),
    ("Seethamahalakshmi", "Seetha mahalaxmi", "match", "SEGMENTATION", "user-contributed: mother's name, 1 word vs 2 words + spelling variant"),
    ("Seeta maha laxmi", "Seetha mahalaxmi", "match", "SEGMENTATION", "user-contributed: mother's name, 3 words vs 2 words"),
    ("Srinivasa rao", "Srinuvasarao", "match", "SEGMENTATION", "user-contributed: 2 words vs 1 fused word + spelling variant"),
    ("Srinuvasarao", "Srinuvas Rao", "match", "SEGMENTATION", "user-contributed: 1 fused word vs 2 words"),

    # ---- HONORIFIC_NEG (honorific present, names still genuinely differ) ----
    ("Shri Ramesh Kumar", "Shri Suresh Kumar", "non_match", "HONORIFIC_NEG", ""),
    ("Smt. Sunita Devi", "Smt. Anita Devi", "non_match", "HONORIFIC_NEG", ""),
    ("Dr. Vikram Singh", "Dr. Vikram Chauhan", "non_match", "HONORIFIC_NEG", "same given name, different surname"),
    ("Mrs. Padma Reddy", "Mrs. Padma Nair", "non_match", "HONORIFIC_NEG", "same given name, different surname"),
    ("Mr. Suresh Gupta", "Mr. Suresh Bhatt", "non_match", "HONORIFIC_NEG", "same given name, different surname"),
    ("Kumari Anjali Sharma", "Kumari Anjali Verma", "non_match", "HONORIFIC_NEG", "same given name, different surname"),
]


def main():
    out_path = os.path.join(os.path.dirname(__file__), "name_pairs.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["pair_id", "name_a", "name_b", "label", "category", "notes"])
        for i, (a, b, label, category, note) in enumerate(PAIRS, start=1):
            writer.writerow([i, a, b, label, category, note])
    n_match = sum(1 for p in PAIRS if p[2] == "match")
    n_non = len(PAIRS) - n_match
    print(f"Wrote {len(PAIRS)} pairs to {out_path} ({n_match} match / {n_non} non_match)")


if __name__ == "__main__":
    main()
