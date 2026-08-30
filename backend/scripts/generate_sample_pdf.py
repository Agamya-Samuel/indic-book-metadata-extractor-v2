"""
Generate sample test PDFs for the Indic Book Metadata Extractor.

Creates realistic book-like PDFs with title pages, copyright info,
dedication, content pages, and colophon — suitable for testing the
full OCR → LLM metadata extraction pipeline.

Usage:
    python scripts/generate_sample_pdf.py
    python scripts/generate_sample_pdf.py --lang tel --quality clean
    python scripts/generate_sample_pdf.py --lang hin --quality degraded
    python scripts/generate_sample_pdf.py --lang eng
    python scripts/generate_sample_pdf.py --all
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import fitz  # PyMuPDF


# ---------------------------------------------------------------------------
# Font discovery — find an Indic-capable font for Telugu/Hindi rendering
# ---------------------------------------------------------------------------

def _find_indic_font() -> str | None:
    """Return path to an Indic-capable TTF font, or None for fallback."""
    candidates = [
        # Windows system fonts
        os.path.expandvars(r"%WINDIR%\Fonts\Nirmala.ttf"),
        os.path.expandvars(r"%WINDIR%\Fonts\Mangal.ttf"),
        os.path.expandvars(r"%WINDIR%\Fonts\NirmalaUI.ttf"),
        # Linux
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansTelugu-Regular.ttf",
        "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
        # macOS
        "/Library/Fonts/NotoSansDevanagari-Regular.otf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


INDIC_FONT_PATH = _find_indic_font()
# Map language -> whether it needs the Indic font
_NEEDS_INDIC = {"tel", "hin"}


# ---------------------------------------------------------------------------
# Book data — one dict per language/quality variant
# ---------------------------------------------------------------------------

BOOKS: dict[str, dict] = {
    # ── Telugu, clean printing ──────────────────────────────────────────────
    "tel_clean": {
        "filename": "sample_tel_clean.pdf",
        "language": "tel",
        "quality": "clean",
        "metadata": {
            "title": "భారత స్వాతంత్ర్య సంగ్రామం",
            "subtitle": "ఒక చారిత్రక అధ్యయనం",
            "author": "డా. రామకృష్ణ శర్మ",
            "publisher": "తెలుగు అకాడమీ",
            "publisher_telugu": "తెలుగు అకాడమీ",
            "place_of_publication": "హైదరాబాద్",
            "publication_date": "2024",
            "isbn": "978-81-234-5678-9",
            "language": "Telugu",
            "original_language": "Telugu",
            "genre": "చారిత్రక గ్రంథం",
            "subject": "భారత స్వాతంత్ర్య ఉద్యమం",
            "edition_number": "మొదటి ముద్రణ",
            "pages": "248",
            "printer": "శ్రీ వెంకటేశ్వర ప్రింటర్స్",
            "place_of_printing": "హైదరాబాద్",
            "translator": None,
            "editor": "ప్రొ. సీతారామయ్య",
            "volume": "1",
            "form_of_creative_work": "పుస్తకం",
            "dedication": "నా తల్లిదండ్రులకు అంకితం",
            "forewords": "ప్రముఖ చరిత్రకారుడు ప్రొ. వెంకటేశ్వరరావు గారి ముందుమాట",
        },
        "pages": [
            # Page 1: Title page
            {
                "type": "title",
                "content": [
                    {"text": "భారత స్వాతంత్ర్య సంగ్రామం", "size": 28, "bold": True, "y": 180},
                    {"text": "ఒక చారిత్రక అధ్యయనం", "size": 18, "y": 230},
                    {"text": "", "size": 14, "y": 290},
                    {"text": "రచయిత", "size": 12, "y": 290},
                    {"text": "డా. రామకృష్ణ శర్మ", "size": 20, "bold": True, "y": 320},
                    {"text": "", "size": 14, "y": 380},
                    {"text": "సంపాదకులు: ప్రొ. సీతారామయ్య", "size": 12, "y": 380},
                    {"text": "", "size": 14, "y": 440},
                    {"text": "తెలుగు అకాడమీ", "size": 16, "bold": True, "y": 450},
                    {"text": "హైదరాబాద్", "size": 14, "y": 480},
                    {"text": "2024", "size": 14, "y": 510},
                ],
            },
            # Page 2: Copyright / publication info
            {
                "type": "copyright",
                "content": [
                    {"text": "ప్రచురణ సమాచారం", "size": 18, "bold": True, "y": 80},
                    {"text": "", "size": 10, "y": 110},
                    {"text": "శీర్షిక: భారత స్వాతంత్ర్య సంగ్రామం", "size": 11, "y": 120},
                    {"text": "ఉపశీర్షిక: ఒక చారిత్రక అధ్యయనం", "size": 11, "y": 145},
                    {"text": "రచయిత: డా. రామకృష్ణ శర్మ", "size": 11, "y": 170},
                    {"text": "సంపాదకులు: ప్రొ. సీతారామయ్య", "size": 11, "y": 195},
                    {"text": "ప్రచురణకర్త: తెలుగు అకాడమీ, హైదరాబాద్", "size": 11, "y": 220},
                    {"text": "ముద్రణ: శ్రీ వెంకటేశ్వర ప్రింటర్స్, హైదరాబాద్", "size": 11, "y": 245},
                    {"text": "మొదటి ముద్రణ: 2024", "size": 11, "y": 270},
                    {"text": "ISBN: 978-81-234-5678-9", "size": 11, "y": 295},
                    {"text": "పేజీలు: 248", "size": 11, "y": 320},
                    {"text": "వాల్యూమ్: 1", "size": 11, "y": 345},
                    {"text": "", "size": 10, "y": 380},
                    {"text": "అన్ని హక్కులు రిజర్వ్ చేయబడ్డాయి.", "size": 10, "y": 390},
                    {"text": "ఈ పుస్తకం యొక్క ఏ భాగాన్నైనా ప్రచురణకర్త", "size": 10, "y": 415},
                    {"text": "అనుమతి లేకుండా పునర్ముద్రించడం నిషేధం.", "size": 10, "y": 435},
                ],
            },
            # Page 3: Dedication
            {
                "type": "dedication",
                "content": [
                    {"text": "అంకితం", "size": 22, "bold": True, "y": 200},
                    {"text": "", "size": 14, "y": 250},
                    {"text": "నా ప్రియమైన తల్లిదండ్రులకు", "size": 16, "y": 270},
                    {"text": "మరియు", "size": 14, "y": 300},
                    {"text": "భారత స్వాతంత్ర్య సమరయోధులందరికీ", "size": 16, "y": 330},
                    {"text": "ఈ గ్రంథాన్ని అంకితం చేస్తున్నాను", "size": 14, "y": 380},
                ],
            },
            # Page 4: Foreword
            {
                "type": "foreword",
                "content": [
                    {"text": "ముందుమాట", "size": 20, "bold": True, "y": 70},
                    {"text": "", "size": 11, "y": 100},
                    {
                        "text": "భారతదేశ స్వాతంత్ర్య సంగ్రామం ప్రపంచ చరిత్రలో ఒక",
                        "size": 12,
                        "y": 110,
                    },
                    {
                        "text": "అద్వితీయమైన ఉద్యమం. ఈ గ్రంథంలో రచయిత",
                        "size": 12,
                        "y": 132,
                    },
                    {
                        "text": "డా. రామకృష్ణ శర్మ గారు 1857 నుండి 1947 వరకు",
                        "size": 12,
                        "y": 154,
                    },
                    {
                        "text": "జరిగిన ముఖ్యమైన సంఘటనలను వివరంగా వివరించారు.",
                        "size": 12,
                        "y": 176,
                    },
                    {"text": "", "size": 11, "y": 200},
                    {
                        "text": "ఈ పుస్తకం విద్యార్థులకు, పరిశోధకులకు మరియు",
                        "size": 12,
                        "y": 210,
                    },
                    {
                        "text": "చరిత్ర ప్రేమికులకు ఒక విలువైన సంపదగా నిలుస్తుంది.",
                        "size": 12,
                        "y": 232,
                    },
                    {"text": "", "size": 11, "y": 270},
                    {"text": "— ప్రొ. వెంకటేశ్వరరావు", "size": 12, "bold": True, "y": 280},
                    {"text": "ఉస్మానియా విశ్వవిద్యాలయం", "size": 11, "y": 302},
                ],
            },
            # Page 5: Content page
            {
                "type": "content",
                "content": [
                    {"text": "అధ్యాయం 1", "size": 18, "bold": True, "y": 70},
                    {"text": "1857 మొదటి స్వాతంత్ర్య సంగ్రామం", "size": 16, "bold": True, "y": 100},
                    {"text": "", "size": 11, "y": 130},
                    {
                        "text": "1857 సంవత్సరం భారతదేశ చరిత్రలో ఒక ముఖ్యమైన",
                        "size": 12,
                        "y": 140,
                    },
                    {
                        "text": "మలుపు. ఈ సంవత్సరం మే 10న మీరట్‌లో ప్రారంభమైన",
                        "size": 12,
                        "y": 162,
                    },
                    {
                        "text": "తిరుగుబాటు త్వరలోనే ఉత్తర భారతదేశమంతటికీ",
                        "size": 12,
                        "y": 184,
                    },
                    {
                        "text": "వ్యాపించింది. మంగల్ పాండే, రాణి లక్ష్మీబాయి,",
                        "size": 12,
                        "y": 206,
                    },
                    {
                        "text": "తాంతియా తోపే వంటి వీరులు ఈ ఉద్యమంలో ప్రముఖ",
                        "size": 12,
                        "y": 228,
                    },
                    {"text": "పాత్ర పోషించారు.", "size": 12, "y": 250},
                    {"text": "", "size": 11, "y": 275},
                    {
                        "text": "బ్రిటిష్ ఈస్ట్ ఇండియా కంపెనీ పాలనలో భారతీయులు",
                        "size": 12,
                        "y": 285,
                    },
                    {
                        "text": "అనుభవించిన అన్యాయాలు, ఆర్థిక దోపిడీ, సాంస్కృతిక",
                        "size": 12,
                        "y": 307,
                    },
                    {
                        "text": "అణచివేత — ఇవన్నీ ఈ తిరుగుబాటుకు కారణాలు.",
                        "size": 12,
                        "y": 329,
                    },
                    {"text": "", "size": 11, "y": 355},
                    {
                        "text": "ఎన్‌ఫీల్డ్ రైఫిల్ తూటాల వ్యవహారం ప్రత్యక్ష",
                        "size": 12,
                        "y": 365,
                    },
                    {
                        "text": "కారణంగా నిలిచింది. ఆవు మరియు పంది కొవ్వుతో",
                        "size": 12,
                        "y": 387,
                    },
                    {
                        "text": "తయారు చేసిన తూటాలను నోటితో తెంచాలనే ఆదేశం",
                        "size": 12,
                        "y": 409,
                    },
                    {
                        "text": "హిందూ మరియు ముస్లిం సైనికుల మత విశ్వాసాలను",
                        "size": 12,
                        "y": 431,
                    },
                    {"text": "గాయపరిచింది.", "size": 12, "y": 453},
                ],
            },
            # Page 6: Colophon
            {
                "type": "colophon",
                "content": [
                    {"text": "కొలోఫోన్", "size": 20, "bold": True, "y": 80},
                    {"text": "", "size": 11, "y": 110},
                    {"text": "భారత స్వాతంత్ర్య సంగ్రామం", "size": 14, "bold": True, "y": 120},
                    {"text": "ఒక చారిత్రక అధ్యయనం", "size": 12, "y": 145},
                    {"text": "", "size": 10, "y": 170},
                    {"text": "రచయిత: డా. రామకృష్ణ శర్మ", "size": 11, "y": 180},
                    {"text": "సంపాదకులు: ప్రొ. సీతారామయ్య", "size": 11, "y": 205},
                    {"text": "", "size": 10, "y": 230},
                    {"text": "ప్రచురణకర్త: తెలుగు అకాడమీ", "size": 11, "y": 240},
                    {"text": "చిరునామా: తెలుగు అకాడమీ, స్టేట్ ఆర్కైవ్స్ కాంప్లెక్స్,", "size": 10, "y": 265},
                    {"text": "తార్నాక, హైదరాబాద్ - 500 007, తెలంగాణ", "size": 10, "y": 285},
                    {"text": "", "size": 10, "y": 310},
                    {"text": "ముద్రణ: శ్రీ వెంకటేశ్వర ప్రింటర్స్", "size": 11, "y": 320},
                    {"text": "మొదటి ముద్రణ: 2024", "size": 11, "y": 345},
                    {"text": "సంచిక సంఖ్య: 1", "size": 11, "y": 370},
                    {"text": "ISBN: 978-81-234-5678-9", "size": 11, "y": 395},
                    {"text": "", "size": 10, "y": 420},
                    {"text": "పేజీలు: 248", "size": 11, "y": 430},
                    {"text": "ధర: ₹ 350", "size": 11, "y": 455},
                    {"text": "", "size": 10, "y": 480},
                    {"text": "ప్రతులకు:", "size": 11, "bold": True, "y": 490},
                    {"text": "తెలుగు అకాడమీ, హైదరాబాద్", "size": 10, "y": 512},
                ],
            },
        ],
    },

    # ── Hindi, clean printing ───────────────────────────────────────────────
    "hin_clean": {
        "filename": "sample_hin_clean.pdf",
        "language": "hin",
        "quality": "clean",
        "metadata": {
            "title": "आधुनिक भारत का इतिहास",
            "subtitle": "स्वतंत्रता से आज तक",
            "author": "डॉ. रमेश चंद्र शर्मा",
            "publisher": "राजकमल प्रकाशन",
            "place_of_publication": "नई दिल्ली",
            "publication_date": "2023",
            "isbn": "978-81-267-1234-5",
            "language": "Hindi",
            "original_language": "Hindi",
            "genre": "इतिहास",
            "subject": "आधुनिक भारतीय इतिहास",
            "edition_number": "तीसरा संस्करण",
            "pages": "320",
            "printer": "नेशनल प्रिंटिंग प्रेस",
            "place_of_printing": "नोएडा",
            "editor": "प्रो. सुरेश मिश्रा",
            "volume": None,
            "form_of_creative_work": "पुस्तक",
            "dedication": "मेरे गुरुजनों को समर्पित",
            "forewords": "प्रसिद्ध इतिहासकार प्रो. बिपन चंद्र जी की भूमिका",
        },
        "pages": [
            # Page 1: Title page
            {
                "type": "title",
                "content": [
                    {"text": "आधुनिक भारत का इतिहास", "size": 28, "bold": True, "y": 180},
                    {"text": "स्वतंत्रता से आज तक", "size": 18, "y": 230},
                    {"text": "", "size": 14, "y": 290},
                    {"text": "लेखक", "size": 12, "y": 290},
                    {"text": "डॉ. रमेश चंद्र शर्मा", "size": 20, "bold": True, "y": 320},
                    {"text": "", "size": 14, "y": 380},
                    {"text": "संपादक: प्रो. सुरेश मिश्रा", "size": 12, "y": 380},
                    {"text": "", "size": 14, "y": 440},
                    {"text": "राजकमल प्रकाशन", "size": 16, "bold": True, "y": 450},
                    {"text": "नई दिल्ली", "size": 14, "y": 480},
                    {"text": "2023", "size": 14, "y": 510},
                ],
            },
            # Page 2: Copyright
            {
                "type": "copyright",
                "content": [
                    {"text": "प्रकाशन सूचना", "size": 18, "bold": True, "y": 80},
                    {"text": "", "size": 10, "y": 110},
                    {"text": "शीर्षक: आधुनिक भारत का इतिहास", "size": 11, "y": 120},
                    {"text": "उपशीर्षक: स्वतंत्रता से आज तक", "size": 11, "y": 145},
                    {"text": "लेखक: डॉ. रमेश चंद्र शर्मा", "size": 11, "y": 170},
                    {"text": "संपादक: प्रो. सुरेश मिश्रा", "size": 11, "y": 195},
                    {"text": "प्रकाशक: राजकमल प्रकाशन, नई दिल्ली", "size": 11, "y": 220},
                    {"text": "मुद्रक: नेशनल प्रिंटिंग प्रेस, नोएडा", "size": 11, "y": 245},
                    {"text": "तीसरा संस्करण: 2023", "size": 11, "y": 270},
                    {"text": "ISBN: 978-81-267-1234-5", "size": 11, "y": 295},
                    {"text": "पृष्ठ संख्या: 320", "size": 11, "y": 320},
                    {"text": "", "size": 10, "y": 355},
                    {"text": "सर्वाधिकार सुरक्षित।", "size": 10, "y": 365},
                    {"text": "इस पुस्तक के किसी भी भाग का पुनर्मुद्रण", "size": 10, "y": 390},
                    {"text": "प्रकाशक की अनुमति के बिना वर्जित है।", "size": 10, "y": 410},
                ],
            },
            # Page 3: Dedication
            {
                "type": "dedication",
                "content": [
                    {"text": "समर्पण", "size": 22, "bold": True, "y": 200},
                    {"text": "", "size": 14, "y": 250},
                    {"text": "मेरे पूज्य गुरुजनों को", "size": 16, "y": 270},
                    {"text": "और", "size": 14, "y": 300},
                    {"text": "भारत माता के सभी सपूतों को", "size": 16, "y": 330},
                    {"text": "यह ग्रंथ समर्पित है", "size": 14, "y": 380},
                ],
            },
            # Page 4: Content
            {
                "type": "content",
                "content": [
                    {"text": "अध्याय 1", "size": 18, "bold": True, "y": 70},
                    {"text": "स्वतंत्रता के बाद का भारत", "size": 16, "bold": True, "y": 100},
                    {"text": "", "size": 11, "y": 130},
                    {"text": "15 अगस्त 1947 को भारत को स्वतंत्रता मिली।", "size": 12, "y": 140},
                    {"text": "पंडित जवाहरलाल नेहरू ने प्रधानमंत्री के रूप में", "size": 12, "y": 162},
                    {"text": "शपथ ली। नए राष्ट्र के निर्माण की चुनौती सामने थी।", "size": 12, "y": 184},
                    {"text": "", "size": 11, "y": 210},
                    {"text": "संविधान सभा ने 26 जनवरी 1950 को भारत का", "size": 12, "y": 220},
                    {"text": "संविधान लागू किया। डॉ. भीमराव अंबेडकर ने", "size": 12, "y": 242},
                    {"text": "संविधान के निर्माण में महत्वपूर्ण भूमिका निभाई।", "size": 12, "y": 264},
                    {"text": "", "size": 11, "y": 290},
                    {"text": "पंचवर्षीय योजनाओं के माध्यम से आर्थिक विकास", "size": 12, "y": 300},
                    {"text": "की नींव रखी गई। कृषि सुधार, औद्योगीकरण और", "size": 12, "y": 322},
                    {"text": "शिक्षा के प्रसार पर विशेष ध्यान दिया गया।", "size": 12, "y": 344},
                ],
            },
            # Page 5: Content continued
            {
                "type": "content",
                "content": [
                    {"text": "अध्याय 2", "size": 18, "bold": True, "y": 70},
                    {"text": "आर्थिक सुधार और विकास", "size": 16, "bold": True, "y": 100},
                    {"text": "", "size": 11, "y": 130},
                    {"text": "1991 में भारत ने आर्थिक उदारीकरण की नीति अपनाई।", "size": 12, "y": 140},
                    {"text": "प्रधानमंत्री पी.वी. नरसिम्हा राव और वित्त मंत्री", "size": 12, "y": 162},
                    {"text": "डॉ. मनमोहन सिंह ने इस सुधार की अगुवाई की।", "size": 12, "y": 184},
                    {"text": "", "size": 11, "y": 210},
                    {"text": "नई आर्थिक नीति ने भारत को वैश्विक अर्थव्यवस्था", "size": 12, "y": 220},
                    {"text": "से जोड़ा। विदेशी निवेश बढ़ा, आईटी उद्योग का", "size": 12, "y": 242},
                    {"text": "विकास हुआ, और मध्यम वर्ग का विस्तार हुआ।", "size": 12, "y": 264},
                ],
            },
            # Page 6: Colophon
            {
                "type": "colophon",
                "content": [
                    {"text": "कोलोफ़ोन", "size": 20, "bold": True, "y": 80},
                    {"text": "", "size": 11, "y": 110},
                    {"text": "आधुनिक भारत का इतिहास", "size": 14, "bold": True, "y": 120},
                    {"text": "स्वतंत्रता से आज तक", "size": 12, "y": 145},
                    {"text": "", "size": 10, "y": 170},
                    {"text": "लेखक: डॉ. रमेश चंद्र शर्मा", "size": 11, "y": 180},
                    {"text": "संपादक: प्रो. सुरेश मिश्रा", "size": 11, "y": 205},
                    {"text": "", "size": 10, "y": 230},
                    {"text": "प्रकाशक: राजकमल प्रकाशन", "size": 11, "y": 240},
                    {"text": "पता: 1, भागीरथ पैलेस, कनॉट प्लेस,", "size": 10, "y": 265},
                    {"text": "नई दिल्ली - 110 001", "size": 10, "y": 285},
                    {"text": "", "size": 10, "y": 310},
                    {"text": "मुद्रक: नेशनल प्रिंटिंग प्रेस, नोएडा", "size": 11, "y": 320},
                    {"text": "तीसरा संस्करण: 2023", "size": 11, "y": 345},
                    {"text": "ISBN: 978-81-267-1234-5", "size": 11, "y": 370},
                    {"text": "", "size": 10, "y": 395},
                    {"text": "पृष्ठ संख्या: 320", "size": 11, "y": 405},
                    {"text": "मूल्य: ₹ 450", "size": 11, "y": 430},
                    {"text": "", "size": 10, "y": 455},
                    {"text": "प्रतियाँ प्राप्त करें:", "size": 11, "bold": True, "y": 465},
                    {"text": "राजकमल प्रकाशन, नई दिल्ली", "size": 10, "y": 487},
                ],
            },
        ],
    },

    # ── English (for basic pipeline testing) ────────────────────────────────
    "eng_clean": {
        "filename": "sample_eng_clean.pdf",
        "language": "eng",
        "quality": "clean",
        "metadata": {
            "title": "The History of Modern India",
            "subtitle": "From Independence to the Present Day",
            "author": "Dr. Ramesh Chandra Sharma",
            "publisher": "National Book Trust",
            "place_of_publication": "New Delhi",
            "publication_date": "2024",
            "isbn": "978-81-234-5678-9",
            "language": "English",
            "original_language": "English",
            "genre": "History",
            "subject": "Modern Indian History",
            "edition_number": "First Edition",
            "pages": "280",
            "printer": "National Printing Press, Noida",
            "place_of_printing": "Noida",
            "editor": "Prof. Suresh Mishra",
            "translator": None,
            "volume": None,
            "form_of_creative_work": "Book",
            "dedication": "To my beloved parents and teachers",
            "forewords": "Foreword by the renowned historian Prof. Bipan Chandra",
        },
        "pages": [
            # Page 1: Title page
            {
                "type": "title",
                "content": [
                    {"text": "The History of Modern India", "size": 28, "bold": True, "y": 180},
                    {"text": "From Independence to the Present Day", "size": 18, "y": 230},
                    {"text": "", "size": 14, "y": 290},
                    {"text": "by", "size": 12, "y": 290},
                    {"text": "Dr. Ramesh Chandra Sharma", "size": 20, "bold": True, "y": 320},
                    {"text": "", "size": 14, "y": 380},
                    {"text": "Edited by Prof. Suresh Mishra", "size": 12, "y": 380},
                    {"text": "", "size": 14, "y": 440},
                    {"text": "National Book Trust", "size": 16, "bold": True, "y": 450},
                    {"text": "New Delhi", "size": 14, "y": 480},
                    {"text": "2024", "size": 14, "y": 510},
                ],
            },
            # Page 2: Copyright
            {
                "type": "copyright",
                "content": [
                    {"text": "Publication Information", "size": 18, "bold": True, "y": 80},
                    {"text": "", "size": 10, "y": 110},
                    {"text": "Title: The History of Modern India", "size": 11, "y": 120},
                    {"text": "Subtitle: From Independence to the Present Day", "size": 11, "y": 145},
                    {"text": "Author: Dr. Ramesh Chandra Sharma", "size": 11, "y": 170},
                    {"text": "Editor: Prof. Suresh Mishra", "size": 11, "y": 195},
                    {"text": "Publisher: National Book Trust, New Delhi", "size": 11, "y": 220},
                    {"text": "Printer: National Printing Press, Noida", "size": 11, "y": 245},
                    {"text": "First Edition: 2024", "size": 11, "y": 270},
                    {"text": "ISBN: 978-81-234-5678-9", "size": 11, "y": 295},
                    {"text": "Pages: 280", "size": 11, "y": 320},
                    {"text": "", "size": 10, "y": 355},
                    {"text": "All rights reserved.", "size": 10, "y": 365},
                    {"text": "No part of this publication may be reproduced", "size": 10, "y": 390},
                    {"text": "without the prior permission of the publisher.", "size": 10, "y": 410},
                ],
            },
            # Page 3: Dedication
            {
                "type": "dedication",
                "content": [
                    {"text": "Dedication", "size": 22, "bold": True, "y": 200},
                    {"text": "", "size": 14, "y": 250},
                    {"text": "To my beloved parents", "size": 16, "y": 270},
                    {"text": "and", "size": 14, "y": 300},
                    {"text": "all the great teachers who shaped my life", "size": 16, "y": 330},
                    {"text": "I dedicate this humble work", "size": 14, "y": 380},
                ],
            },
            # Page 4: Content
            {
                "type": "content",
                "content": [
                    {"text": "Chapter 1", "size": 18, "bold": True, "y": 70},
                    {"text": "India After Independence", "size": 16, "bold": True, "y": 100},
                    {"text": "", "size": 11, "y": 130},
                    {"text": "On 15 August 1947, India achieved independence from", "size": 12, "y": 140},
                    {"text": "British colonial rule. Pandit Jawaharlal Nehru took", "size": 12, "y": 162},
                    {"text": "office as the first Prime Minister of free India.", "size": 12, "y": 184},
                    {"text": "", "size": 11, "y": 210},
                    {"text": "The Constituent Assembly adopted the Constitution", "size": 12, "y": 220},
                    {"text": "of India on 26 January 1950. Dr. B.R. Ambedkar", "size": 12, "y": 242},
                    {"text": "played a pivotal role as the Chairman of the", "size": 12, "y": 264},
                    {"text": "Drafting Committee.", "size": 12, "y": 286},
                    {"text": "", "size": 11, "y": 310},
                    {"text": "Five-Year Plans were introduced to guide the", "size": 12, "y": 320},
                    {"text": "economic development of the nation. Land reforms,", "size": 12, "y": 342},
                    {"text": "industrialization, and expansion of education", "size": 12, "y": 364},
                    {"text": "were the key priorities of the new government.", "size": 12, "y": 386},
                ],
            },
            # Page 5: Content continued
            {
                "type": "content",
                "content": [
                    {"text": "Chapter 2", "size": 18, "bold": True, "y": 70},
                    {"text": "Economic Liberalization", "size": 16, "bold": True, "y": 100},
                    {"text": "", "size": 11, "y": 130},
                    {"text": "In 1991, India embarked on a path of economic", "size": 12, "y": 140},
                    {"text": "liberalization under Prime Minister P.V. Narasimha", "size": 12, "y": 162},
                    {"text": "Rao and Finance Minister Dr. Manmohan Singh.", "size": 12, "y": 184},
                    {"text": "", "size": 11, "y": 210},
                    {"text": "The New Economic Policy opened India to global", "size": 12, "y": 220},
                    {"text": "markets. Foreign investment increased, the IT", "size": 12, "y": 242},
                    {"text": "industry flourished, and a new middle class", "size": 12, "y": 264},
                    {"text": "emerged, transforming the economic landscape.", "size": 12, "y": 286},
                ],
            },
            # Page 6: Colophon
            {
                "type": "colophon",
                "content": [
                    {"text": "Colophon", "size": 20, "bold": True, "y": 80},
                    {"text": "", "size": 11, "y": 110},
                    {"text": "The History of Modern India", "size": 14, "bold": True, "y": 120},
                    {"text": "From Independence to the Present Day", "size": 12, "y": 145},
                    {"text": "", "size": 10, "y": 170},
                    {"text": "Author: Dr. Ramesh Chandra Sharma", "size": 11, "y": 180},
                    {"text": "Editor: Prof. Suresh Mishra", "size": 11, "y": 205},
                    {"text": "", "size": 10, "y": 230},
                    {"text": "Publisher: National Book Trust", "size": 11, "y": 240},
                    {"text": "Address: Nehru Bhawan, 5 Institutional Area,", "size": 10, "y": 265},
                    {"text": "Vasant Kunj, New Delhi - 110 070", "size": 10, "y": 285},
                    {"text": "", "size": 10, "y": 310},
                    {"text": "Printer: National Printing Press, Noida", "size": 11, "y": 320},
                    {"text": "First Edition: 2024", "size": 11, "y": 345},
                    {"text": "ISBN: 978-81-234-5678-9", "size": 11, "y": 370},
                    {"text": "", "size": 10, "y": 395},
                    {"text": "Pages: 280", "size": 11, "y": 405},
                    {"text": "Price: Rs. 395", "size": 11, "y": 430},
                ],
            },
        ],
    },
    # ── Hindi, modern (post-2000) fictional novel ───────────────────────────
    "hin_modern": {
        "filename": "sample_hin_modern.pdf",
        "language": "hin",
        "quality": "modern",
        "metadata": {
            "title": "नदी के दो किनारे",
            "subtitle": "एक उपन्यास",
            "author": "सुनीता शर्मा",
            "publisher": "राजकमल प्रकाशन",
            "publisher_telugu": None,
            "place_of_publication": "नई दिल्ली",
            "publication_date": "2018",
            "isbn": "978-81-267-1234-5",
            "language": "Hindi",
            "original_language": "Hindi",
            "genre": "उपन्यास",
            "subject": "भारतीय सामाजिक जीवन",
            "edition_number": "दूसरा संस्करण",
            "pages": "320",
            "printer": "कमल प्रिंटर्स",
            "place_of_printing": "नोएडा",
            "translator": None,
            "editor": "अनिल कुमार",
            "volume": "1",
            "form_of_creative_work": "पुस्तक",
            "dedication": "अपने गाँव को",
            "forewords": "वरिष्ठ साहित्यकार श्री रमेश शर्मा जी की भूमिका",
        },
        "pages": [
            {
                "content": [
                    {"text": "नदी के दो किनारे", "size": 24, "y": 100, "bold": True},
                    {"text": "एक उपन्यास", "size": 16, "y": 145},
                    {"text": "", "size": 10, "y": 200},
                    {"text": "सुनीता शर्मा", "size": 18, "y": 250},
                    {"text": "", "size": 10, "y": 320},
                    {"text": "राजकमल प्रकाशन", "size": 14, "y": 380},
                    {"text": "नई दिल्ली", "size": 12, "y": 410},
                ],
            },
            {
                "content": [
                    {"text": "ISBN: 978-81-267-1234-5", "size": 11, "y": 100},
                    {"text": "Sankshya: 320", "size": 11, "y": 130},
                    {"text": "Mulya: Rs. 450", "size": 11, "y": 160},
                    {"text": "", "size": 10, "y": 200},
                    {"text": "Prakashak: राजकमल प्रकाशन", "size": 11, "y": 220},
                    {"text": "Pratham Sanskaran: 2018", "size": 11, "y": 245},
                ],
            },
            {
                "content": [
                    {"text": "अपने गाँव को", "size": 14, "y": 300, "italic": True},
                ],
            },
            {
                "content": [
                    {"text": "अध्याय 1", "size": 16, "y": 100, "bold": True},
                    {"text": "नदी के दो किनारे पर बसे दो गाँवों की कहानी...", "size": 12, "y": 140},
                ],
            },
        ],
    },
    # ── Telugu, degraded (low-quality scan simulation) ───────────────────────
    "tel_degraded": {
        "filename": "sample_tel_degraded.pdf",
        "language": "tel",
        "quality": "degraded",
        "metadata": {
            "title": "ఆంధ్ర సాహిత్య చరిత్ర",
            "subtitle": "ప్రాచీన యుగం నుండి ఆధునిక యుగం వరకు",
            "author": "ప్రొ. కాళీపట్నం రామారావు",
            "publisher": "విశాలాంధ్ర పబ్లిషింగ్ హౌస్",
            "publisher_telugu": "విశాలాంధ్ర పబ్లిషింగ్ హౌస్",
            "place_of_publication": "హైదరాబాద్",
            "publication_date": "2015",
            "isbn": "978-81-7894-234-1",
            "language": "Telugu",
            "original_language": "Telugu",
            "genre": "విద్యా సాహిత్యం",
            "subject": "తెలుగు సాహిత్య చరిత్ర",
            "edition_number": "మూడవ ముద్రణ",
            "pages": "456",
            "printer": "శ్రీ గణపతి ప్రింటర్స్",
            "place_of_printing": "సికింద్రాబాద్",
            "translator": None,
            "editor": "డా. విశ్వనాథ సత్యనారాయణ",
            "volume": "2",
            "form_of_creative_work": "గ్రంథం",
            "dedication": "ఆంధ్ర మాతృభాషా భక్తులకు",
            "forewords": "ప్రముఖ సాహిత్య విమర్శకులు ప్రొ. జి. నాగేశ్వరరావు గారి ముందుమాట",
        },
        "pages": [
            {
                "content": [
                    {"text": "ఆంధ్ర సాహిత్య చరిత్ర", "size": 22, "y": 100, "bold": True},
                    {"text": "ప్రాచీన యుగం నుండి ఆధునిక యుగం వరకు", "size": 14, "y": 140},
                    {"text": "", "size": 10, "y": 200},
                    {"text": "ప్రొ. కాళీపట్నం రామారావు", "size": 16, "y": 250},
                    {"text": "", "size": 10, "y": 320},
                    {"text": "విశాలాంధ్ర పబ్లిషింగ్ హౌస్", "size": 14, "y": 380},
                    {"text": "హైదరాబాద్", "size": 12, "y": 410},
                ],
            },
            {
                "content": [
                    {"text": "ISBN: 978-81-7894-234-1", "size": 10, "y": 100},
                    {"text": "Pustaka Sankhya: 456", "size": 10, "y": 130},
                    {"text": "Mulya: Rs. 595", "size": 10, "y": 160},
                    {"text": "", "size": 8, "y": 200},
                    {"text": "Prakashak: విశాలాంధ్ర పబ్లిషింగ్ హౌస్", "size": 10, "y": 220},
                    {"text": "Mooduta Muddran: 2015", "size": 10, "y": 245},
                ],
            },
            {
                "content": [
                    {"text": "సంపాదకులు: డా. విశ్వనాథ సత్యనారాయణ", "size": 10, "y": 100},
                ],
            },
            {
                "content": [
                    {"text": "ఆంధ్ర మాతృభాషా భక్తులకు", "size": 12, "y": 300, "italic": True},
                ],
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

def _draw_text_block(
    page: fitz.Page,
    block: dict,
    page_width: float,
    fontname: str = "helv",
    fontfile: str | None = None,
    font_obj: fitz.Font | None = None,
) -> None:
    """Insert a single text block onto a page, centered horizontally."""
    text = block["text"]
    size = block["size"]
    y = block["y"]

    # Center text horizontally — use Font object for custom fonts
    if font_obj:
        text_width = font_obj.text_length(text, fontsize=size)
    else:
        text_width = fitz.get_text_length(text, fontname=fontname, fontsize=size)
    x = max(72, (page_width - text_width) / 2)

    # Insert text — use fontfile for Indic scripts
    kwargs = dict(fontsize=size, fontname=fontname)
    if fontfile:
        kwargs["fontfile"] = fontfile
    page.insert_text((x, y), text, **kwargs)


def generate_pdf(book_key: str, output_dir: Path) -> Path:
    """Generate a single sample PDF and return its path."""
    book = BOOKS[book_key]
    doc = fitz.open()

    page_width = 595  # A4 width in points
    page_height = 842  # A4 height in points

    # Determine font: use Indic font for Telugu/Hindi if available
    fontname = "helv"
    fontfile = None
    font_obj = None
    if book["language"] in _NEEDS_INDIC and INDIC_FONT_PATH:
        fontname = "indic"
        fontfile = INDIC_FONT_PATH
        font_obj = fitz.Font(fontfile=fontfile)

    for page_data in book["pages"]:
        page = doc.new_page(width=page_width, height=page_height)

        # Register font on each page (required by PyMuPDF)
        if fontfile:
            page.insert_font(fontname=fontname, fontfile=fontfile)

        for block in page_data["content"]:
            _draw_text_block(
                page, block, page_width,
                fontname=fontname, fontfile=fontfile, font_obj=font_obj,
            )

    output_path = output_dir / book["filename"]
    doc.save(str(output_path))
    doc.close()
    return output_path


def update_expected_metadata(book_key: str, fixtures_dir: Path) -> Path:
    """Update (or create) the expected_metadata.json fixture for a book."""
    book = BOOKS[book_key]
    lang = book["language"]
    quality = book["quality"]

    fixture_dir = fixtures_dir / lang / quality
    fixture_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = fixture_dir / "expected_metadata.json"

    recommended_pages = [1, 2, 3, len(book["pages"]) - 1, len(book["pages"])]

    fixture_data = {
        "description": f"Sample {lang.upper()} book with {quality} printing.",
        "language": lang,
        "quality": quality,
        "total_pages": len(book["pages"]),
        "recommended_pages": recommended_pages,
        "expected_metadata": book["metadata"],
        "notes": (
            f"Sample PDF generated by scripts/generate_sample_pdf.py. "
            f"Place 'sample.pdf' in this directory."
        ),
    }

    fixture_path.write_text(json.dumps(fixture_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return fixture_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sample test PDFs")
    parser.add_argument(
        "--lang",
        choices=["tel", "hin", "eng"],
        help="Language to generate (default: all)",
    )
    parser.add_argument(
        "--quality",
        choices=["clean", "degraded", "modern"],
        default="clean",
        help="Quality variant (default: clean)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate all language variants",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for PDFs (default: tests/fixtures/samples/<lang>/<quality>/)",
    )
    parser.add_argument(
        "--skip-fixtures",
        action="store_true",
        help="Skip updating expected_metadata.json fixtures",
    )

    args = parser.parse_args()

    # Resolve paths
    project_root = Path(__file__).resolve().parent.parent
    fixtures_dir = project_root / "tests" / "fixtures" / "samples"

    if args.all:
        keys = list(BOOKS.keys())
    elif args.lang:
        key = f"{args.lang}_{args.quality}"
        if key not in BOOKS:
            print(f"Error: no book data for '{key}'", file=sys.stderr)
            sys.exit(1)
        keys = [key]
    else:
        keys = list(BOOKS.keys())

    for key in keys:
        book = BOOKS[key]
        out_dir = args.output_dir or (fixtures_dir / book["language"] / book["quality"])
        out_dir.mkdir(parents=True, exist_ok=True)

        pdf_path = generate_pdf(key, out_dir)
        print(f"  [OK] Generated: {pdf_path}")

        # Also copy as sample.pdf (what the fixture expects)
        sample_path = out_dir / "sample.pdf"
        sample_path.write_bytes(pdf_path.read_bytes())
        print(f"  [OK] Copied to: {sample_path}")

        if not args.skip_fixtures:
            fixture_path = update_expected_metadata(key, fixtures_dir)
            print(f"  [OK] Fixture:   {fixture_path}")

        print()


if __name__ == "__main__":
    main()
