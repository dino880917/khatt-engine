"""
Arabic Name Lookup Table
Canonical Arabic spellings for common names.
Multiple romanizations map to the same correct Arabic form.

Design decision: lookup table only — no algorithmic transliteration.
Arabic names have canonical spellings that must be correct, not
approximated. If a name is not found, we say so rather than guess.
"""

NAMES = {
    # ═══════════════════════════════════
    # MALE NAMES
    # ═══════════════════════════════════

    # Ahmed / Ahmad
    "ahmed":        "أحمد",
    "ahmad":        "أحمد",
    "achmed":       "أحمد",

    # Mohammed / Muhammad
    "mohammed":     "محمد",
    "muhammad":     "محمد",
    "mohamed":      "محمد",
    "mohammad":     "محمد",
    "mehmet":       "محمد",

    # Ali
    "ali":          "علي",

    # Omar / Umar
    "omar":         "عمر",
    "umar":         "عمر",
    "omer":         "عمر",

    # Hassan / Hasan
    "hassan":       "حسن",
    "hasan":        "حسن",

    # Hussein / Husayn
    "hussein":      "حسين",
    "husain":       "حسين",
    "husayn":       "حسين",
    "hossein":      "حسين",

    # Ibrahim / Abraham
    "ibrahim":      "إبراهيم",
    "ebrahim":      "إبراهيم",

    # Khalid
    "khalid":       "خالد",
    "khaled":       "خالد",

    # Yusuf / Joseph
    "yusuf":        "يوسف",
    "yousef":       "يوسف",
    "yousuf":       "يوسف",
    "joseph":       "يوسف",

    # Abdullah
    "abdullah":     "عبد الله",
    "abdallah":     "عبد الله",
    "abdellah":     "عبد الله",

    # Abdulrahman
    "abdulrahman":  "عبد الرحمن",
    "abdelrahman":  "عبد الرحمن",
    "abdurrahman":  "عبد الرحمن",

    # Mahmoud / Mahmud
    "mahmoud":      "محمود",
    "mahmud":       "محمود",
    "mahmood":      "محمود",

    # Mustafa
    "mustafa":      "مصطفى",
    "mostafa":      "مصطفى",

    # Tariq
    "tariq":        "طارق",
    "tarek":        "طارق",
    "tarik":        "طارق",

    # Bilal
    "bilal":        "بلال",

    # Karim
    "karim":        "كريم",
    "kareem":       "كريم",

    # Samir
    "samir":        "سمير",
    "sameer":       "سمير",

    # Nasser / Nasir
    "nasser":       "ناصر",
    "nasir":        "ناصر",
    "naser":        "ناصر",

    # Hamid / Hameed
    "hamid":        "حامد",
    "hameed":       "حامد",

    # Walid
    "walid":        "وليد",
    "waleed":       "وليد",

    # Sami
    "sami":         "سامي",

    # Adil / Adel
    "adil":         "عادل",
    "adel":         "عادل",

    # Rami
    "rami":         "رامي",

    # Faisal
    "faisal":       "فيصل",
    "faissal":      "فيصل",
    "faysal":       "فيصل",

    # Salim / Selim
    "salim":        "سليم",
    "selim":        "سليم",
    "saleem":       "سليم",

    # Younis / Yunus / Jonah
    "younis":       "يونس",
    "yunus":        "يونس",
    "younes":       "يونس",

    # Idris
    "idris":        "إدريس",

    # Anas
    "anas":         "أنس",

    # Zaid / Zayd
    "zaid":         "زيد",
    "zayd":         "زيد",
    "zayed":        "زيد",

    # Mansour / Mansur
    "mansour":      "منصور",
    "mansur":       "منصور",
    "mansoor":      "منصور",

    # Jamal
    "jamal":        "جمال",
    "gamal":        "جمال",

    # Nabil
    "nabil":        "نبيل",
    "nabeel":       "نبيل",

    # Hadi
    "hadi":         "هادي",

    # Amr
    "amr":          "عمرو",

    # Suleiman / Solomon
    "suleiman":     "سليمان",
    "sulayman":     "سليمان",
    "sulaiman":     "سليمان",
    "solomon":      "سليمان",

    # Dawud / David
    "dawud":        "داود",
    "dawood":       "داود",

    # Musa / Moses
    "musa":         "موسى",
    "moussa":       "موسى",

    # Isa / Jesus
    "isa":          "عيسى",

    # Adam
    "adam":         "آدم",

    # Harun / Aaron
    "harun":        "هارون",
    "haroun":       "هارون",

    # Marwan
    "marwan":       "مروان",

    # Osama / Usama
    "osama":        "أسامة",
    "usama":        "أسامة",

    # Talib
    "talib":        "طالب",

    # Rashid
    "rashid":       "راشد",
    "rashed":       "راشد",

    # Mazen / Mazin
    "mazen":        "مازن",
    "mazin":        "مازن",

    # Khaled — already have Khalid
    "khaled":       "خالد",

    # Aziz
    "aziz":         "عزيز",
    "azziz":        "عزيز",

    # Basem / Basim
    "basem":        "باسم",
    "basim":        "باسم",
    "bassem":       "باسم",

    # Issam
    "issam":        "عصام",
    "isam":         "عصام",

    # Emad / Imad
    "emad":         "عماد",
    "imad":         "عماد",

    # ═══════════════════════════════════
    # FEMALE NAMES
    # ═══════════════════════════════════

    # Fatima
    "fatima":       "فاطمة",
    "fatimah":      "فاطمة",
    "fatema":       "فاطمة",

    # Aisha / Ayesha
    "aisha":        "عائشة",
    "ayesha":       "عائشة",
    "aisha":        "عائشة",

    # Maryam / Mariam
    "maryam":       "مريم",
    "mariam":       "مريم",
    "miriam":       "مريم",

    # Zainab / Zaynab
    "zainab":       "زينب",
    "zaynab":       "زينب",
    "zenab":        "زينب",

    # Layla / Leila
    "layla":        "ليلى",
    "leila":        "ليلى",
    "lila":         "ليلى",

    # Nour / Noor
    "nour":         "نور",
    "noor":         "نور",
    "nur":          "نور",

    # Sara / Sarah
    "sara":         "سارة",
    "sarah":        "سارة",

    # Rania
    "rania":        "رانيا",
    "raniya":       "رانيا",

    # Hana / Hanna
    "hana":         "هناء",
    "hanna":        "هناء",
    "hanaa":        "هناء",

    # Amira
    "amira":        "أميرة",
    "ameera":       "أميرة",

    # Salma
    "salma":        "سلمى",

    # Samira
    "samira":       "سميرة",
    "sameera":      "سميرة",

    # Yasmin / Jasmine
    "yasmin":       "ياسمين",
    "yasmine":      "ياسمين",
    "jasmine":      "ياسمين",

    # Dina / Deena
    "dina":         "دينا",
    "deena":        "دينا",

    # Lina
    "lina":         "لينا",
    "leena":        "لينا",

    # Rana
    "rana":         "رنا",

    # Hind
    "hind":         "هند",

    # Rima
    "rima":         "ريما",
    "reema":        "ريما",

    # Manar
    "manar":        "منار",

    # Ghada
    "ghada":        "غادة",

    # Suha
    "suha":         "سها",

    # Nadia
    "nadia":        "نادية",

    # Mona / Muna
    "mona":         "منى",
    "muna":         "منى",

    # Heba / Hiba
    "heba":         "هبة",
    "hiba":         "هبة",

    # Asma / Asma'
    "asma":         "أسماء",
    "asmaa":        "أسماء",

    # Wafa
    "wafa":         "وفاء",

    # Abeer / Abir
    "abeer":        "عبير",
    "abir":         "عبير",

    # Rouba / Ruba
    "ruba":         "ربى",
    "rouba":        "ربى",

    # Samar
    "samar":        "سمر",

    # Lubna
    "lubna":        "لبنى",

    # Khadija / Khadijah
    "khadija":      "خديجة",
    "khadijah":     "خديجة",
    "khadidja":     "خديجة",

    # Sumaya / Sumayyah
    "sumaya":       "سمية",
    "sumayyah":     "سمية",

    # Israa
    "israa":        "إسراء",
    "isra":         "إسراء",

    # Eman / Iman
    "eman":         "إيمان",
    "iman":         "إيمان",

    # Nada
    "nada":         "ندى",

    # May / Mai
    "may":          "مي",
    "mai":          "مي",

    # Rim
    "rim":          "ريم",

    # ═══════════════════════════════════
    # GENDER NEUTRAL / UNISEX
    # ═══════════════════════════════════

    "nour":         "نور",
    "iman":         "إيمان",

    # ═══════════════════════════════════
    # POPULAR COMPOUND NAMES
    # ═══════════════════════════════════

    "abdelaziz":    "عبد العزيز",
    "abdelkarim":   "عبد الكريم",
    "abdelnasser":  "عبد الناصر",
    "abdulaziz":    "عبد العزيز",
    "abdulkarim":   "عبد الكريم",
    "abdulmalik":   "عبد الملك",
    "abdulhamid":   "عبد الحميد",
}


def lookup(name: str) -> dict:
    """
    Look up a name and return result dict.

    Returns:
        {
            "found": True,
            "arabic": "محمد",
            "input": "Mohammed"
        }
        or
        {
            "found": False,
            "arabic": None,
            "input": "Xyzabc"
        }
    """
    key = name.strip().lower().replace("-", "").replace(" ", "")
    arabic = NAMES.get(key)

    return {
        "found":   arabic is not None,
        "arabic":  arabic,
        "input":   name,
    }


def search(partial: str) -> list:
    """
    Search for names starting with the given prefix.
    Returns list of (romanized, arabic) tuples for autocomplete.
    """
    key      = partial.strip().lower()
    seen     = set()
    results  = []

    for roman, arabic in NAMES.items():
        if roman.startswith(key) and arabic not in seen:
            seen.add(arabic)
            results.append({
                "romanized": roman.capitalize(),
                "arabic":    arabic,
            })

    return sorted(results, key=lambda x: x["romanized"])[:8]