"""Spoken text in English, Tamil and Hindi.

Every sentence the user hears comes from here, so adding a language
means adding one more block to TEXT.
"""

LANGS = {"en": "English", "ta": "தமிழ்", "hi": "हिन्दी"}

# words people might use when asking for a language
_ALIASES = {
    "en": ["en", "english", "eng"],
    "ta": ["ta", "tamil", "தமிழ்", "tamizh", "thamizh"],
    "hi": ["hi", "hindi", "हिन्दी", "हिंदी"],
}

TEXT = {
    "en": {
        "briefing": ("Sea briefing for {zone}. Waves are {wave_now} metres now, up to {wave_max} metres "
                     "in the next {hours} hours. Wind is {wind} km/h, with gusts up to {gust} km/h around {gust_time}. "
                     "{rain} Trip risk: {level}, because of {reason}."),
        "risk": "{level} for {zone}: {reason} expected in the next {hours} hours. {advice}",
        "rain_high": "Rain chance up to {rain} percent.",
        "rain_low": "Little chance of rain.",
        "level": {"safe": "Safe", "caution": "Caution", "danger": "Don't go"},
        "cause": {"wave": "waves up to {value} metres",
                  "gust": "wind gusts up to {value} km/h",
                  "calm": "waves under 1.5 metres and gusts under 30 km/h"},
        "advice": {"safe": "Conditions look fine for a trip.",
                   "caution": "Go only if you must, stay close to shore, and keep checking.",
                   "danger": "Please stay ashore today."},
        "saved": "Got it, {user}. Your usual zone is {zone}. Ask me for your sea briefing any time.",
        "unknown_zone": "I don't know the zone '{zone}'. I know: {zones}.",
        "no_saved_zone": "I don't have a saved zone for {user} yet. Tell me your usual zone first. I know: {zones}.",
        "fetch_failed": "Sorry, I couldn't get the sea forecast for {zone} right now. Please try again in a minute.",
        "need_name": "Please tell me your name first.", "today": "today", "tomorrow": "tomorrow",
        "best_now": "Safe to set out now from {zone}, until about {end}. Plan to be back before then.",
        "best_later": "Best time to go from {zone}: {start} to {end}, when conditions are expected to be safe.",
        "best_caution": "No fully safe window in the next 24 hours for {zone}. The calmest stretch is {start} to {end}, rated Caution.",
        "best_none": "No safe window in the next 24 hours for {zone}. Please stay ashore.",
        "trip_started": "Trip logged, {user}. Heading to {zone}, back by {back}. Right now the trip risk is {level}. Your family can ask SeaSense if you are back.",
        "trip_ended": "Welcome back, {user}. Your trip is closed.",
        "no_trip": "{user} has no trip logged right now.",
        "bad_back_by": "Please tell me when you expect to be back, like 2 PM, 14:00 or 8 hours.",
        "trip_at_sea": "{user} left for {zone} at {left} and is expected back by {back}, in about {remaining}.",
        "trip_overdue": ("{user} is overdue. Left for {zone} at {left} and was expected back by {back}, {late} ago. "
                         "Try calling first. If you can't reach them, call the Coast Guard on {cg}."),
        "trip_returned": "{user} is back. Returned at {time}.",
        "trip_worse": "Warning: sea conditions at {zone} have worsened since departure at {left}. Now: {level}, because of {reason}.",
    },
    "ta": {
        "briefing": ("{zone} கடல் நிலை அறிக்கை. தற்போது அலைகள் {wave_now} மீட்டர் உயரம், அடுத்த {hours} மணி நேரத்தில் "
                     "{wave_max} மீட்டர் வரை உயரலாம். காற்றின் வேகம் மணிக்கு {wind} கிலோமீட்டர், {gust_time} அளவில் "
                     "மணிக்கு {gust} கிலோமீட்டர் வரை பலத்த காற்று வீசலாம். {rain} பயண அபாயம்: {level}. காரணம்: {reason}."),
        "risk": "{zone}: {level}. அடுத்த {hours} மணி நேர முன்னறிவிப்பு: {reason}. {advice}",
        "rain_high": "மழை பெய்ய {rain} சதவீதம் வரை வாய்ப்பு உள்ளது.",
        "rain_low": "மழை வாய்ப்பு குறைவு.",
        "level": {"safe": "பாதுகாப்பானது", "caution": "எச்சரிக்கை", "danger": "கடலுக்குச் செல்ல வேண்டாம்"},
        "cause": {"wave": "{value} மீட்டர் வரை உயரமான அலைகள்",
                  "gust": "மணிக்கு {value} கிலோமீட்டர் வரை பலத்த காற்று",
                  "calm": "அலைகள் 1.5 மீட்டருக்குக் குறைவு, காற்று மணிக்கு 30 கிலோமீட்டருக்குக் குறைவு"},
        "advice": {"safe": "கடல் பயணத்திற்கு நிலைமை சரியாக உள்ளது.",
                   "caution": "அவசியமென்றால் மட்டும் செல்லுங்கள், கரைக்கு அருகிலேயே இருங்கள், நிலைமையைத் தொடர்ந்து கவனியுங்கள்.",
                   "danger": "இன்று தயவுசெய்து கரையிலேயே இருங்கள்."},
        "saved": "சரி, {user}. உங்கள் வழக்கமான மீன்பிடி பகுதி {zone}. எப்போது வேண்டுமானாலும் கடல் நிலை அறிக்கையைக் கேளுங்கள்.",
        "unknown_zone": "'{zone}' என்ற பகுதி எனக்குத் தெரியாது. எனக்குத் தெரிந்தவை: {zones}.",
        "no_saved_zone": "{user} அவர்களுக்கு இன்னும் பகுதி சேமிக்கப்படவில்லை. முதலில் உங்கள் வழக்கமான பகுதியைச் சொல்லுங்கள். எனக்குத் தெரிந்தவை: {zones}.",
        "fetch_failed": "மன்னிக்கவும், {zone} கடல் முன்னறிவிப்பை இப்போது பெற முடியவில்லை. ஒரு நிமிடம் கழித்து மீண்டும் முயலுங்கள்.",
        "need_name": "முதலில் உங்கள் பெயரைச் சொல்லுங்கள்.", "today": "இன்று", "tomorrow": "நாளை",
        "best_now": "{zone}: இப்போது புறப்படலாம், ஆனால் சுமார் {end} வரை மட்டுமே பாதுகாப்பானது. அதற்கு முன் திரும்பத் திட்டமிடுங்கள்.",
        "best_later": "{zone}: புறப்பட சிறந்த நேரம் {start} முதல் {end} வரை. அப்போது நிலைமை பாதுகாப்பாக இருக்கும் என எதிர்பார்க்கப்படுகிறது.",
        "best_caution": "{zone}: அடுத்த 24 மணி நேரத்தில் முழுமையாகப் பாதுகாப்பான நேரம் இல்லை. ஒப்பீட்டளவில் அமைதியான நேரம் {start} முதல் {end} வரை, எச்சரிக்கை நிலை.",
        "best_none": "{zone}: அடுத்த 24 மணி நேரத்தில் பாதுகாப்பான நேரம் இல்லை. தயவுசெய்து கரையிலேயே இருங்கள்.",
        "trip_started": "பயணம் பதிவு செய்யப்பட்டது, {user}. {zone} நோக்கிச் செல்கிறீர்கள், {back}க்குள் திரும்புவீர்கள். தற்போதைய பயண அபாயம்: {level}. நீங்கள் திரும்பிவிட்டீர்களா என உங்கள் குடும்பத்தினர் SeaSense-இடம் கேட்கலாம்.",
        "trip_ended": "மீண்டும் வருக, {user}. உங்கள் பயணம் முடிந்தது.",
        "no_trip": "{user} அவர்களுக்கு இப்போது பதிவு செய்யப்பட்ட பயணம் இல்லை.",
        "bad_back_by": "எப்போது திரும்புவீர்கள் என்று சொல்லுங்கள், உதாரணமாக 2 PM, 14:00 அல்லது 8 hours.",
        "trip_at_sea": "{user} {left}க்கு {zone} நோக்கிப் புறப்பட்டார். {back}க்குள் திரும்ப வேண்டும், இன்னும் சுமார் {remaining}.",
        "trip_overdue": ("{user} இன்னும் திரும்பவில்லை. {left}க்கு {zone} நோக்கிப் புறப்பட்டார், {back}க்குள் திரும்பியிருக்க வேண்டும், {late} தாமதம். "
                         "முதலில் அவரை அழைத்துப் பாருங்கள். தொடர்பு கொள்ள முடியவில்லை என்றால், கடலோரக் காவல்படையை {cg} என்ற எண்ணில் அழையுங்கள்."),
        "trip_returned": "{user} திரும்பிவிட்டார். {time}க்குத் திரும்பினார்.",
        "trip_worse": "எச்சரிக்கை: {left}க்குப் புறப்பட்டதிலிருந்து {zone} கடல் நிலை மோசமடைந்துள்ளது. இப்போது: {level}. காரணம்: {reason}.",
    },
    "hi": {
        "briefing": ("{zone} के लिए समुद्री रिपोर्ट। अभी लहरें {wave_now} मीटर ऊँची हैं, अगले {hours} घंटों में {wave_max} मीटर "
                     "तक जा सकती हैं। हवा की गति {wind} किलोमीटर प्रति घंटा है, {gust_time} के आसपास झोंके {gust} किलोमीटर "
                     "प्रति घंटा तक पहुँच सकते हैं। {rain} यात्रा जोखिम: {level}। कारण: {reason}।"),
        "risk": "{zone}: {level}। अगले {hours} घंटों का अनुमान: {reason}। {advice}",
        "rain_high": "बारिश की संभावना {rain} प्रतिशत तक है।",
        "rain_low": "बारिश की संभावना कम है।",
        "level": {"safe": "सुरक्षित", "caution": "सावधान", "danger": "समुद्र में न जाएँ"},
        "cause": {"wave": "{value} मीटर तक ऊँची लहरें",
                  "gust": "{value} किलोमीटर प्रति घंटा तक तेज़ हवा के झोंके",
                  "calm": "लहरें 1.5 मीटर से कम और झोंके 30 किलोमीटर प्रति घंटा से कम"},
        "advice": {"safe": "यात्रा के लिए हालात ठीक हैं।",
                   "caution": "ज़रूरी हो तभी जाएँ, किनारे के पास रहें और हालात पर नज़र रखें।",
                   "danger": "आज कृपया किनारे पर ही रहें।"},
        "saved": "ठीक है, {user}। आपका सामान्य क्षेत्र {zone} है। कभी भी अपनी समुद्री रिपोर्ट पूछें।",
        "unknown_zone": "मुझे '{zone}' क्षेत्र की जानकारी नहीं है। मैं इन्हें जानता हूँ: {zones}।",
        "no_saved_zone": "{user} के लिए अभी कोई क्षेत्र सेव नहीं है। पहले अपना सामान्य क्षेत्र बताइए। मैं इन्हें जानता हूँ: {zones}।",
        "fetch_failed": "माफ़ कीजिए, अभी {zone} का समुद्री पूर्वानुमान नहीं मिल पाया। एक मिनट बाद फिर कोशिश करें।",
        "need_name": "पहले अपना नाम बताइए।", "today": "आज", "tomorrow": "कल",
        "best_now": "{zone}: अभी निकल सकते हैं, लेकिन लगभग {end} तक ही सुरक्षित है। उससे पहले लौटने की योजना बनाएँ।",
        "best_later": "{zone}: निकलने का सबसे अच्छा समय {start} से {end} तक है, जब हालात सुरक्षित रहने की उम्मीद है।",
        "best_caution": "{zone}: अगले 24 घंटों में पूरी तरह सुरक्षित समय नहीं है। सबसे शांत समय {start} से {end} तक है, स्तर: सावधान।",
        "best_none": "{zone}: अगले 24 घंटों में कोई सुरक्षित समय नहीं है। कृपया किनारे पर ही रहें।",
        "trip_started": "यात्रा दर्ज हो गई, {user}। आप {zone} जा रहे हैं, {back} तक लौटेंगे। अभी यात्रा जोखिम: {level}। आपका परिवार SeaSense से पूछ सकता है कि आप लौटे या नहीं।",
        "trip_ended": "वापसी पर स्वागत है, {user}। आपकी यात्रा बंद हो गई।",
        "no_trip": "{user} की अभी कोई यात्रा दर्ज नहीं है।",
        "bad_back_by": "बताइए कि आप कब तक लौटेंगे, जैसे 2 PM, 14:00 या 8 hours।",
        "trip_at_sea": "{user} {left} {zone} के लिए निकले थे और {back} तक लौटने वाले हैं, लगभग {remaining} बाकी।",
        "trip_overdue": ("{user} अभी तक नहीं लौटे। {left} {zone} के लिए निकले थे, {back} तक लौटना था, {late} की देरी। "
                         "पहले उन्हें फ़ोन करें। संपर्क न हो तो तटरक्षक बल को {cg} पर कॉल करें।"),
        "trip_returned": "{user} लौट आए हैं। {time} लौटे।",
        "trip_worse": "चेतावनी: {left} निकलने के बाद से {zone} में समुद्र के हालात बिगड़ गए हैं। अभी: {level}। कारण: {reason}।",
    },
}


def normalize_lang(text: str | None) -> str:
    """'Tamil', 'ta', 'தமிழ்' -> 'ta'. Unknown or empty -> 'en'."""
    said = (text or "").strip().lower()
    for code, words in _ALIASES.items():
        if said in words:
            return code
    return "en"


def t(lang: str, key: str, **values) -> str:
    return TEXT[lang][key].format(**values)


def spoken_hour(hour: int, lang: str, minute: int = 0) -> str:
    """Time of day (IST) as people say it: '8:30 PM', 'இரவு 8:30 மணி', 'रात 8:30 बजे'."""
    h12 = hour % 12 or 12
    h12 = f"{h12}:{minute:02d}" if minute else str(h12)
    if lang == "en":
        return f"{h12} {'AM' if hour < 12 else 'PM'}"
    if 2 <= hour < 5:
        part = {"ta": "அதிகாலை", "hi": "तड़के"}[lang]
    elif 5 <= hour < 12:
        part = {"ta": "காலை", "hi": "सुबह"}[lang]
    elif 12 <= hour < 16:
        part = {"ta": "மதியம்", "hi": "दोपहर"}[lang]
    elif 16 <= hour < 19:
        part = {"ta": "மாலை", "hi": "शाम"}[lang]
    else:
        part = {"ta": "இரவு", "hi": "रात"}[lang]
    return f"{part} {h12} மணி" if lang == "ta" else f"{part} {h12} बजे"
