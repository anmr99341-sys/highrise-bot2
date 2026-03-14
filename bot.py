import asyncio
import random
import sys
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from highrise import BaseBot, User, Position, RoomPermissions, AnchorPosition, Item, CurrencyItem
from highrise.models import SessionMetadata
from highrise.__main__ import main as hr_main, BotDefinition
import httpx
import re
import unicodedata


# Resolve encoding issues on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

print(">>> SCRIPT STARTED <<<")

BASE_DIR = Path(__file__).parent

class MyBot(BaseBot):
    def __init__(self, room_id=None, runner=None, bot_name=None):
        super().__init__()
        self.room_id = room_id
        self.runner = runner
        self.bot_name = bot_name
        self.owners = ["NMR0"]  # 👑 قائمة الملاك (يُضاف المالك تلقائياً أو عبر المانجر)
        self.admins = [""]  # قائمة المشرفين
        self.vip_users = []  # ⭐ قائمة VIP
        self.distinguished_users = []  # ✨ قائمة المتميزين (محميين من التفاعلات)
        self.muted_users = {}  # المستخدمين المكتومين
        self.frozen_users = {}  # المستخدمين المجمدين
        self.user_floors = {}   # تتبع طابق كل مستخدم للنقل الذكي
        self.warned_users = {}  # المستخدمين المحذرين
        self.auto_mod = True  # التحكم التلقائي الشامل
        self.begging_protection = True  # نظام حماية من الشحادة
        self.insult_protection = True   # نظام حماية من السب
        self.spam_protection = True  # الحماية من السبام
        self.smart_teleport = True  # 🚀 ميزة النقل السريع (تبديل الطوابق بمجرد النقر)
        self.user_messages = {}  # تتبع رسائل المستخدمين للحماية من السبام
        self.interaction_history = set()  # 📨 مستخدمين تفاعلوا مع البوت (رسائل خاصة أو جولد)
        self.welcome_message = ""  # رسالة الترحيب (اتركه فارغاً ليقوم البوت بالترحيب باسم الروم تلقائياً)
        self.custom_welcomes = {}   # رسائل ترحيب خاصة لأشخاص محددين
        self.welcome_public = True  # الترحيب في الشات العام
        self.banned_words = []  # الكلمات المحظورة
        self.room_name = "بوت الإدارة" # اسم الروم الحالي
        self.bot_id = None # معرف البوت
        self.outfit = [] # 👕 ملابس البوت المحفوظة
        self.cached_usernames = {} # 📝 ذاكرة مؤقتة لأسماء المستخدمين لتسريع الأداء
        self.heart_shortcuts = {}    # ❤️ اختصارات إرسال 50 قلب (حرف -> يوزر)
        self.room_owner_username = None # 👑 اسم المالك الأصلي للروم (محمي من الإزالة)
        self.violation_counts = {}   # ⚠️ عداد الإنذارات
        self.active_reaction_loops = {} # {requester_id: {"task": task, "target": name, "type": type}}
        self._tip_buffer = {} # {user_id: {"amount": int, "task": task}}
        
        # --- Mistral AI Configuration ---
        self.mistral_api_key = "w0kWQS7LGgUCnpF7vEaHDFYG875Wx6RE"
        self.ai_client = httpx.AsyncClient(timeout=30.0)
        self.conversation_history = {}  # 🧠 ذاكرة المحادثة لكل مستخدم (user_id -> list of messages)

        
        
        
        # 🏢 إحداثيات الطوابق (افتراضية - يمكنك تعديلها بالوقوف في مكان وكتابة: تعيين_طابق)
        self.floors = {
            "ground": Position(9.5, 0.0, 14.5, "FrontLeft"),      # الأرضية
            "floor1": Position(14.5, 7.5, 13.5, "FrontLeft"),     # فوق
            "floor2": Position(15.5, 13.75, 6.5, "FrontRight"),    # فوق2
            "vip":    Position(12.0, 13.75, 0.5, "FrontLeft"),     # VIP
        }
        self.carpets = [] # 🗺️ السجادات الذكية المحددة بالروم
        
        
        # 🤖 موقع البوت الافتراضي (يمكنك تعديله بالوقوف في مكان وكتابة: setbot)
        self.bot_position = Position(9.5, 0.0, 14.5, "FrontLeft")
        
        # تحديد ملف الإعدادات بناءً على اسم البوت أو الغرفة
        if getattr(self, 'bot_name', None):
            safe_name = self.bot_name.lstrip("@").lower()
            self.config_file = str(BASE_DIR / f"bot_config_{safe_name}.json")
            self.config_file_adjusted = True
        elif self.room_id:
            self.config_file = str(BASE_DIR / f"bot_config_{self.room_id}.json")
            self.config_file_adjusted = True
        else:
            self.config_file = str(BASE_DIR / "bot_config.json")
            self.config_file_adjusted = False
            
        self.load_config()
        
        # 🎭 نظام الرقصات - أسماء نصية مع دعم للأرقام عبر القائمة
        self.emotes = {
            "Floating": {"id": "emote-float", "dur": 8, "ar": ["طفو", "تحليق"]},
            "SleighRide": {"id": "emote-sleigh", "dur": 9, "ar": ["زلاجة", "تزلج"]},
            "EmoteFashionista": {"id": "emote-fashionista", "dur": 5, "ar": ["فاشن", "موضة"]},
            "Cheerful": {"id": "emote-pose8", "dur": 4, "ar": ["مبتهج", "بهجة"]},
            "DanceIcecream": {"id": "dance-icecream", "dur": 14, "ar": ["ايسكريم", "بوظة"]},
            "Macarena": {"id": "dance-macarena", "dur": 12, "ar": ["ماكرينا", "مكارينا"]},
            "EmbracingModel": {"id": "emote-pose7", "dur": 4, "ar": ["موديل_احتضان"]},
            "ShuffleDance": {"id": "dance-tiktok10", "dur": 8, "ar": ["شافل", "خلط"]},
            "LambisPose": {"id": "emote-superpose", "dur": 4, "ar": ["بوز_سوبر"]},
            "GraveDance": {"id": "dance-weird", "dur": 21, "ar": ["رقص_غريب"]},
            "ViralGroove": {"id": "dance-tiktok9", "dur": 11, "ar": ["فايرال", "رقص_تيك"]},
            "EmoteCute": {"id": "emote-cute", "dur": 6, "ar": ["كيوت", "لطيف"]},
            "TheWave": {"id": "emote-wave", "dur": 2.5, "ar": ["موجة", "هاي"]},
            "Kiss": {"id": "emote-kiss", "dur": 2, "ar": ["بوسه", "قبلة", "بوس"]},
            "Laugh": {"id": "emote-laughing", "dur": 2.5, "ar": ["ضحك", "هههه"]},
            "Sweating": {"id": "emote-hot", "dur": 4, "ar": ["عرق", "حر"]},
            "ImACutie": {"id": "emote-cutey", "dur": 3, "ar": ["كيوتي", "حلو"]},
            "FashionPose": {"id": "emote-pose5", "dur": 4, "ar": ["بوز_فاشن"]},
            "Teleport": {"id": "emote-teleporting", "dur": 11, "ar": ["تليبورت", "انتقال"]},
            "LetsGoShopping": {"id": "dance-shoppingcart", "dur": 4, "ar": ["تسوق", "شوبنق"]},
            "GreedyEmote": {"id": "emote-greedy", "dur": 4, "ar": ["طماع", "جشع"]},
            "IChallengeYou": {"id": "emote-pose3", "dur": 5, "ar": ["تحدي"]},
            "FlirtyWink": {"id": "emote-pose1", "dur": 2, "ar": ["غمز"]},
            "EmotePunkguitar": {"id": "emote-punkguitar", "dur": 9, "ar": ["قيتار_بانك", "جيتار"]},
            "SingAlong": {"id": "idle_singing", "dur": 9.5, "ar": ["غناء", "اغنية"]},
            "ACasualDance": {"id": "idle-dance-casual", "dur": 8.5, "ar": ["رقص_عادي"]},
            "Confusion": {"id": "emote-confused", "dur": 8, "ar": ["حيرة", "محتار"]},
            "RaiseTheRoof": {"id": "emoji-celebrate", "dur": 3, "ar": ["سقف", "رفع_السقف"]},
            "SaunterSway": {"id": "dance-anime", "dur": 8, "ar": ["انمي", "رقص_انمي"]},
            "SwordFight": {"id": "emote-swordfight", "dur": 5, "ar": ["سيف", "قتال"]},
            "BashfulBlush": {"id": "emote-shy2", "dur": 4.5, "ar": ["خجل", "استحياء"]},
            "SaySoDance": {"id": "idle-dance-tiktok4", "dur": 15, "ar": ["سي_سو", "تيكتوك4"]},
            "DontStartNow": {"id": "dance-tiktok2", "dur": 10, "ar": ["تيكتوك2"]},
            "Model": {"id": "emote-model", "dur": 6, "ar": ["موديل", "عارض"]},
            "Charging": {"id": "emote-charging", "dur": 8, "ar": ["شحن", "طاقة"]},
            "DoTheWorm": {"id": "emote-snake", "dur": 5, "ar": ["دودة", "ثعبان"]},
            "RussianDance": {"id": "dance-russian", "dur": 10.25, "ar": ["رقص_روسي", "روسي"]},
            "UWUMood": {"id": "idle-uwu", "dur": 24, "ar": ["يو_دبليو_يو"]},
            "Clap": {"id": "emoji-clapping", "dur": 2, "ar": ["تصفيقة"]},
            "Happy": {"id": "emote-happy", "dur": 2, "ar": ["سعيد", "فرحان"]},
            "DanceWrong": {"id": "dance-wrong", "dur": 12, "ar": ["رقص_غلط"]},
            "TummyAche": {"id": "emoji-gagging", "dur": 5, "ar": ["مغص", "بطن"]},
            "SavageDance": {"id": "dance-tiktok8", "dur": 10, "ar": ["سافج", "وحشي"]},
            "KPopDance": {"id": "dance-blackpink", "dur": 6.5, "ar": ["كيبوب"]},
            "PennysDance": {"id": "dance-pennywise", "dur": 0.5, "ar": ["بيني"]},
            "Bow": {"id": "emote-bow", "dur": 3, "ar": ["انحناء", "انحناءة"]},
            "Curtsy": {"id": "emote-curtsy", "dur": 2, "ar": ["تنوره", "انحناءه"]},
            "SnowballFight": {"id": "emote-snowball", "dur": 5, "ar": ["ثلج", "كرة_ثلج"]},
            "SnowAngel": {"id": "emote-snowangel", "dur": 6, "ar": ["ملاك_ثلج"]},
            "Telekinesis": {"id": "emote-telekinesis", "dur": 10, "ar": ["تحريك_عقلي"]},
            "Maniac": {"id": "emote-maniac", "dur": 4.5, "ar": ["مجنون", "جنون"]},
            "EnergyBall": {"id": "emote-energyball", "dur": 7, "ar": ["كرة_طاقة"]},
            "FroggieHop": {"id": "demote-frog", "dur": 14, "ar": ["ضفدع", "نط_ضفدع"]},
            "Sit": {"id": "idle-loop-sitfloor", "dur": 22, "ar": ["جلوس", "اجلس", "قعود"]},
            "Hyped": {"id": "emote-hyped", "dur": 7, "ar": ["حماس", "متحمس"]},
            "JingleHop": {"id": "dance-jinglebell", "dur": 10.5, "ar": ["جنقل", "عيد_الميلاد"]},
            "BitNervous": {"id": "idle-nervous", "dur": 21, "ar": ["عصبي", "توتر"]},
            "GottaGo": {"id": "idle-toilet", "dur": 31.5, "ar": ["حمام", "لازم_اروح"]},
            "ZeroGravity": {"id": "emote-astronaut", "dur": 13, "ar": ["فضاء", "رائد"]},
            "Timejump": {"id": "emote-timejump", "dur": 4, "ar": ["قفز_زمني"]},
            "GroovyPenguin": {"id": "dance-pinguin", "dur": 11, "ar": ["بطريق", "بنغوين"]},
            "CreepyPuppet": {"id": "dance-creepypuppet", "dur": 6, "ar": ["دمية_مخيفة"]},
            "EmoteGravity": {"id": "emote-gravity", "dur": 8, "ar": ["جاذبية"]},
            "ZombieRun": {"id": "emote-zombierun", "dur": 9, "ar": ["ركض_زومبي"]},
            "Enthused": {"id": "idle-enthusiastic", "dur": 15, "ar": ["متحمس_جدا", "حماسة"]},
            "KawaiiGoGo": {"id": "dance-kawai", "dur": 10, "ar": ["كاواي"]},
            "Repose": {"id": "sit-relaxed", "dur": 29, "ar": ["استرخاء", "راحة"]},
            "Shy": {"id": "emote-shy", "dur": 4, "ar": ["خجول", "استحي"]},
            "No": {"id": "emote-no", "dur": 2, "ar": ["لا", "رفض"]},
            "Sad": {"id": "emote-sad", "dur": 4.5, "ar": ["حزين", "زعلان", "حزن"]},
            "Yes": {"id": "emote-yes", "dur": 2, "ar": ["نعم", "اي", "موافق"]},
            "Hello": {"id": "emote-hello", "dur": 2.5, "ar": ["مرحبا", "هلا", "اهلا"]},
            "Tired": {"id": "emote-tired", "dur": 4, "ar": ["تعبان", "تعب"]},
            "Angry": {"id": "emoji-angry", "dur": 5, "ar": ["غاضب", "معصب", "غضب"]},
            "ThumbsUp": {"id": "emoji-thumbsup", "dur": 2, "ar": ["ابهام", "ممتاز"]},
            "Stargazing": {"id": "emote-stargazer", "dur": 7, "ar": ["نجوم", "تامل_نجوم"]},
            "AirGuitar": {"id": "idle-guitar", "dur": 12, "ar": ["قيتار", "جيتار_هوائي"]},
            "Revelations": {"id": "emote-headblowup", "dur": 11, "ar": ["صدمة", "انفجار_راس"]},
            "WatchYourBack": {"id": "emote-creepycute", "dur": 7, "ar": ["انتبه", "خلف"]},
            "Arabesque": {"id": "emote-pose10", "dur": 3.5, "ar": ["ارابيسك"]},
            "PartyTime": {"id": "emote-celebrate", "dur": 3, "ar": ["حفلة", "احتفال"]},
            "IceSkating": {"id": "emote-iceskating", "dur": 7, "ar": ["تزلج_جليد"]},
            "ReadyToRumble": {"id": "emote-boxer", "dur": 5, "ar": ["ملاكمة", "بوكس"]},
            "Scritchy": {"id": "idle-wild", "dur": 25, "ar": ["حكة", "هرش"]},
            "ThisIsForYou": {"id": "emote-gift", "dur": 5, "ar": ["هدية", "هديه"]},
            "PushIt": {"id": "dance-employee", "dur": 6, "ar": ["دفع", "ادفع"]},
            "BigSurprise": {"id": "emote-pose6", "dur": 5, "ar": ["مفاجأة", "مفاجاة"]},
            "SweetLittleMoves": {"id": "dance-touch", "dur": 11, "ar": ["حركات_حلوة"]},
            "CelebrationStep": {"id": "emote-celebrationstep", "dur": 3, "ar": ["خطوة_احتفال"]},
            "Launch": {"id": "emote-launch", "dur": 9, "ar": ["اطلاق", "انطلاق"]},
            "CuteSalute": {"id": "emote-cutesalute", "dur": 2.5, "ar": ["تحية_لطيفة"]},
            "AtAttention": {"id": "emote-salute", "dur": 3, "ar": ["تحية", "سلام"]},
            "WopDance": {"id": "dance-tiktok11", "dur": 9, "ar": ["ووب", "تيكتوك11"]},
            "DitzyPose": {"id": "emote-pose9", "dur": 4, "ar": ["بوز_دتزي"]},
            "SweetSmooch": {"id": "emote-kissing", "dur": 5, "ar": ["بوسه_حلوة"]},
            "FairyFloat": {"id": "idle-floating", "dur": 24, "ar": ["طيران_خيالي", "جنية"]},
            "FairyTwirl": {"id": "emote-looping", "dur": 7, "ar": ["دوران_جنية"]},
            "Casting": {"id": "fishing-cast", "dur": 1, "ar": ["صيد_رمي"]},
            "NowWeWait": {"id": "fishing-idle", "dur": 15, "ar": ["انتظار_صيد"]},
            "MiningMine": {"id": "mining-mine", "dur": 3, "ar": ["تعدين"]},
            "LandingAFish": {"id": "fishing-pull", "dur": 1, "ar": ["سحب_سمكة"]},
            "WeHaveAStrike": {"id": "fishing-pull-small", "dur": 1, "ar": ["سمكة_صغيرة"]},
            "MiningSuccess": {"id": "mining-success", "dur": 3, "ar": ["تعدين_ناجح"]},
            "IgnitionBoost": {"id": "hcc-jetpack", "dur": 19, "ar": ["جت_باك", "صاروخ"]},
            "Rest": {"id": "sit-open", "dur": 26.025963, "ar": ["ريست", "راحه"]},
            "ريست": {"id": "sit-open", "dur": 26.025963, "ar": ["ريست", "راحه"]},
            "Aerobics": {"id": "idle-loop-aerobics", "dur": 8, "ar": ["ايروبكس", "رياضه"]},
            "Amused": {"id": "emote-laughing2", "dur": 5, "ar": ["مستمتع", "ضحك2"]},
            "Arrogance": {"id": "emoji-arrogance", "dur": 6, "ar": ["غرور", "تكبر"]},
            "Attentive": {"id": "idle_layingdown", "dur": 24, "ar": ["منتبه", "مستلقي"]},
            "BlastOff": {"id": "emote-disappear", "dur": 6, "ar": ["اختفاء", "انطلق"]},
            "Boo": {"id": "emote-boo", "dur": 4, "ar": ["بوو", "تخويف"]},
            "Cheer": {"id": "dance-cheerleader", "dur": 17, "ar": ["تشجيع"]},
            "CozyNap": {"id": "idle-floorsleeping", "dur": 13, "ar": ["قيلولة", "نوم_ارض"]},
            "Dab": {"id": "emote-dab", "dur": 2, "ar": ["داب"]},
            "DuckWalk": {"id": "dance-duckwalk", "dur": 11, "ar": ["مشي_بطة", "بطة"]},
            "ElbowBump": {"id": "emote-elbowbump", "dur": 3, "ar": ["كوع"]},
            "FallingApart": {"id": "emote-apart", "dur": 4, "ar": ["تفكك", "انهيار"]},
            "Fighter": {"id": "idle-fighter", "dur": 17, "ar": ["مقاتل"]},
            "FruityDance": {"id": "dance-fruity", "dur": 16, "ar": ["رقص_فواكه"]},
            "GangnamStyle": {"id": "emote-gangnam", "dur": 6.5, "ar": ["جانجنام", "كانكنام"]},
            "Gasp": {"id": "emoji-scared", "dur": 2.5, "ar": ["خوف", "فزع"]},
            "Ghost": {"id": "emoji-ghost", "dur": 3, "ar": ["شبح"]},
            "GhostFloat": {"id": "emote-ghost-idle", "dur": 19, "ar": ["جوست", "شبح_طائر"]},
            "جوست": {"id": "emote-ghost-idle", "dur": 19, "ar": ["جوست", "شبح_طائر"]},
            "GimmeAttention": {"id": "emote-attention", "dur": 4, "ar": ["انتباه", "اهتمام"]},
            "Handstand": {"id": "emote-handstand", "dur": 3.5, "ar": ["وقوف_يدين"]},
            "HarlemShake": {"id": "emote-harlemshake", "dur": 13, "ar": ["هارلم_شيك"]},
            "HipShake": {"id": "dance-hipshake", "dur": 12, "ar": ["هز_وسط"]},
            "ImaginaryJetpack": {"id": "emote-jetpack", "dur": 16, "ar": ["جت_باك_خيالي"]},
            "Irritated": {"id": "idle-angry", "dur": 24, "ar": ["متضايق"]},
            "KarmaDance": {"id": "dance-wild", "dur": 13, "ar": ["كارما", "رقص_بري"]},
            "LaidBack": {"id": "sit-open", "dur": 25, "ar": ["مسترخي"]},
            "Levitate": {"id": "emoji-halo", "dur": 5.5, "ar": ["تحليق_هالة", "هالة"]},
            "LoveFlutter": {"id": "emote-hearteyes", "dur": 3.5, "ar": ["عيون_قلب", "حب_عيون"]},
            "Lying": {"id": "emoji-lying", "dur": 5.5, "ar": ["كذب", "كذاب"]},
            "Magnetic": {"id": "dance-tiktok14", "dur": 9.5, "ar": ["مغناطيس"]},
            "MindBlown": {"id": "emoji-mind-blown", "dur": 2, "ar": ["عقل_منفجر", "ذهول"]},
            "MoonlitHowl": {"id": "emote-howl", "dur": 5.5, "ar": ["عواء"]},
            "Moonwalk": {"id": "emote-gordonshuffle", "dur": 7.5, "ar": ["مون_ووك", "مونووك"]},
            "NightFever": {"id": "emote-nightfever", "dur": 5, "ar": ["حمى_الليل"]},
            "NinjaRun": {"id": "emote-ninjarun", "dur": 4, "ar": ["نينجا", "ركض_نينجا"]},
            "NocturnalHowl": {"id": "idle-howl", "dur": 30, "ar": ["عواء_ليلي"]},
            "OrangeJuiceDance": {"id": "dance-orangejustice", "dur": 5.5, "ar": ["عصير_برتقال"]},
            "Panic": {"id": "emote-panic", "dur": 2, "ar": ["هلع", "ذعر"]},
            "Peekaboo": {"id": "emote-peekaboo", "dur": 3.5, "ar": ["بيكابو", "استغماية"]},
            "PissedOff": {"id": "emote-frustrated", "dur": 4.5, "ar": ["زهق", "منرفز"]},
            "PossessedPuppet": {"id": "emote-puppet", "dur": 16, "ar": ["دمية"]},
            "Punch": {"id": "emoji-punch", "dur": 1, "ar": ["لكمة", "لكم"]},
            "PushUps": {"id": "dance-aerobics", "dur": 8, "ar": ["تمارين", "جيم", "رياضة"]},
            "Rainbow": {"id": "emote-rainbow", "dur": 2.5, "ar": ["قوس_قزح"]},
            "Relaxed": {"id": "idle_layingdown2", "dur": 20.5, "ar": ["استرخاء2", "ريلاكس", "استرخاء"]},
            "Relaxing": {"id": "idle-floorsleeping2", "dur": 16, "ar": ["استرخاء_نوم"]},
            "Renegade": {"id": "idle-dance-tiktok7", "dur": 12, "ar": ["رينيقيد"]},
            "Revival": {"id": "emote-death", "dur": 6, "ar": ["احياء", "موت"]},
            "RingOnIt": {"id": "dance-singleladies", "dur": 20.5, "ar": ["خاتم", "سنقل_ليديز"]},
            "ROFL": {"id": "emote-rofl", "dur": 6, "ar": ["ضحك_تدحرج"]},
            "Robot": {"id": "emote-robot", "dur": 7, "ar": ["روبوت", "ربوت"]},
            "RockOut": {"id": "dance-metal", "dur": 14.5, "ar": ["روك", "ميتال"]},
            "Roll": {"id": "emote-roll", "dur": 3, "ar": ["تدحرج"]},
            "SecretHandshake": {"id": "emote-secrethandshake", "dur": 3, "ar": ["مصافحة_سرية"]},
            "Shrink": {"id": "emote-shrink", "dur": 8, "ar": ["تقلص", "صغر"]},
            "Slap": {"id": "emote-slap", "dur": 2, "ar": ["صفعة", "كف"]},
            "Smoothwalk": {"id": "dance-smoothwalk", "dur": 5.5, "ar": ["مشي_ناعم"]},
            "Stinky": {"id": "emoji-poop", "dur": 4, "ar": ["نتن", "ريحة"]},
            "SuperKick": {"id": "emote-kicking", "dur": 4.5, "ar": ["رفسة", "رفس"]},
            "SuperRun": {"id": "emote-superrun", "dur": 6, "ar": ["ركض_سريع"]},
            "TapDance": {"id": "emote-tapdance", "dur": 10.5, "ar": ["رقص_تاب"]},
            "TapLoop": {"id": "idle-loop-tapdance", "dur": 6, "ar": ["تاب_لوب"]},
            "Trampoline": {"id": "emote-trampoline", "dur": 5, "ar": ["ترامبولين", "نطاطة"]},
            "ZombieDance": {"id": "dance-zombie", "dur": 12, "ar": ["رقص_زومبي"]},
            "Annoyed": {"id": "idle-loop-annoyed", "dur": 16.5, "ar": ["منزعج2", "ازعاج"]},
            "Bummed": {"id": "idle-loop-sad", "dur": 28, "ar": ["محبط", "كئيب"]},
            "BunnyHop": {"id": "emote-bunnyhop", "dur": 11, "ar": ["ارنب", "نط_ارنب"]},
            "Chillin": {"id": "idle-loop-happy", "dur": 18, "ar": ["رايق", "مرتاح"]},
            "Clumsy": {"id": "emote-fail2", "dur": 6, "ar": ["اخرق", "وقعة"]},
            "Collapse": {"id": "emote-death2", "dur": 4, "ar": ["انهيار2", "سقوط"]},
            "Cold": {"id": "emote-cold", "dur": 3, "ar": ["برد", "بارد"]},
            "Disco": {"id": "emote-disco", "dur": 4.5, "ar": ["ديسكو"]},
            "Embarrassed": {"id": "emote-embarrassed", "dur": 7, "ar": ["محرج", "احراج"]},
            "Exasperated": {"id": "emote-exasperated", "dur": 2, "ar": ["مستاء"]},
            "EyeRoll": {"id": "emoji-eyeroll", "dur": 2.5, "ar": ["تدوير_عيون"]},
            "FacePalm": {"id": "emote-exasperatedb", "dur": 2, "ar": ["فيس_بالم"]},
            "Faint": {"id": "emote-fainting", "dur": 17.5, "ar": ["اغماء", "اغماءة"]},
            "FaintDrop": {"id": "emote-deathdrop", "dur": 3, "ar": ["سقوط_مفاجئ"]},
            "Fall": {"id": "emote-fail1", "dur": 5.5, "ar": ["وقوع", "طيحة"]},
            "Fatigued": {"id": "idle-loop-tired", "dur": 21, "ar": ["ارهاق", "مرهق"]},
            "FeelTheBeat": {"id": "idle-dance-headbobbing", "dur": 24.5, "ar": ["ايقاع", "هز_راس"]},
            "FireballLunge": {"id": "emoji-hadoken", "dur": 2, "ar": ["كرة_نار", "هادوكن"]},
            "GiveUp": {"id": "emoji-give-up", "dur": 5, "ar": ["استسلام", "يأس"]},
            "HandsInTheAir": {"id": "dance-handsup", "dur": 21.5, "ar": ["ايدين_فوق"]},
            "HeartHands": {"id": "emote-heartfingers", "dur": 3.5, "ar": ["قلب_بالايد"]},
            "HeroPose": {"id": "idle-hero", "dur": 21, "ar": ["بطل", "سوبرمان"]},
            "HomeRun": {"id": "emote-baseball", "dur": 6.5, "ar": ["بيسبول"]},
            "HugYourself": {"id": "emote-hugyourself", "dur": 4.5, "ar": ["حضن_نفسك"]},
            "IBelieveICanFly": {"id": "emote-wings", "dur": 12.5, "ar": ["اجنحة", "طيران"]},
            "Jump": {"id": "emote-jumpb", "dur": 3, "ar": ["قفز", "نط"]},
            "JudoChop": {"id": "emote-judochop", "dur": 2, "ar": ["جودو", "كاراتيه"]},
            "LevelUp": {"id": "emote-levelup", "dur": 5.5, "ar": ["ترقية", "ليفل_اب"]},
            "MonsterFail": {"id": "emote-monster_fail", "dur": 4, "ar": ["وحش_فشل"]},
            "Naughty": {"id": "emoji-naughty", "dur": 4, "ar": ["شقي", "مشاغب"]},
            "PartnerHeartArms": {"id": "emote-heartshape", "dur": 5.5, "ar": ["قلب_ايدين"]},
            "PartnerHug": {"id": "emote-hug", "dur": 3, "ar": ["حضن", "عناق"]},
            "Peace": {"id": "emote-peace", "dur": 5, "ar": ["سلام_علامة", "بيس"]},
            "Point": {"id": "emoji-there", "dur": 1.5, "ar": ["اشارة", "هناك"]},
            "Ponder": {"id": "idle-lookup", "dur": 21, "ar": ["تفكير", "تأمل"]},
            "Posh": {"id": "idle-posh", "dur": 21, "ar": ["فخم", "اناقة"]},
            "PoutyFace": {"id": "idle-sad", "dur": 24, "ar": ["زعل", "وجه_حزين"]},
            "Pray": {"id": "emoji-pray", "dur": 4, "ar": ["دعاء", "صلاة"]},
            "Proposing": {"id": "emote-proposing", "dur": 4, "ar": ["خطبة", "عرض_زواج"]},
            "RopePull": {"id": "emote-ropepull", "dur": 8, "ar": ["سحب_حبل"]},
            "Sick": {"id": "emoji-sick", "dur": 4.5, "ar": ["مريض"]},
            "Sleepy": {"id": "idle-sleep", "dur": 38, "ar": ["نوم", "نعسان"]},
            "Smirk": {"id": "emoji-smirking", "dur": 4, "ar": ["ابتسامة_ماكرة"]},
            "Sneeze": {"id": "emoji-sneeze", "dur": 2.5, "ar": ["عطس", "عطاس"]},
            "Sob": {"id": "emoji-crying", "dur": 3, "ar": ["بكاء", "بكى"]},
            "SplitsDrop": {"id": "emote-splitsdrop", "dur": 4, "ar": ["سبليت", "شقلبة"]},
            "Stunned": {"id": "emoji-dizzy", "dur": 3.5, "ar": ["مذهول", "دوخة"]},
            "SumoFight": {"id": "emote-sumo", "dur": 10, "ar": ["سومو"]},
            "SuperPunch": {"id": "emote-superpunch", "dur": 3, "ar": ["لكمة_خارقة"]},
            "Theatrical": {"id": "emote-theatrical", "dur": 8, "ar": ["مسرحي", "تمثيل"]},
            "Think": {"id": "emote-think", "dur": 3, "ar": ["تفكير2", "فكر"]},
            "ThumbSuck": {"id": "emote-suckthumb", "dur": 3.5, "ar": ["مص_ابهام"]},
            "VogueHands": {"id": "dance-voguehands", "dur": 8.5, "ar": ["فوغ"]},
            "WiggleDance": {"id": "dance-sexy", "dur": 11.5, "ar": ["هز", "رقص_مثير"]},
            "Zombie": {"id": "idle_zombie", "dur": 28, "ar": ["زومبي"]},
            "DanceShuffle": {"id": "dance-shuffle", "dur": 7, "ar": ["شافل2"]},
            "EmoteConfused2": {"id": "emote-confused2", "dur": 7, "ar": ["حيرة2"]},
            "EmoteFail3": {"id": "emote-fail3", "dur": 6, "ar": ["فشل"]},
            "EmoteReceiveDisappointed": {"id": "emote-receive-disappointed", "dur": 5.5, "ar": ["خيبة_امل"]},
            "EmoteReceiveHappy": {"id": "emote-receive-happy", "dur": 4, "ar": ["استلام_سعيد"]},
            "IdleCold": {"id": "idle-cold", "dur": 10, "ar": ["برد_شديد"]},
            "IdleTough": {"id": "idle_tough", "dur": 10, "ar": ["قوي", "صلب"]},
            "MiningFail": {"id": "mining-fail", "dur": 2.5, "ar": ["تعدين_فاشل"]},
            "RunVertical": {"id": "run-vertical", "dur": 1, "ar": ["ركض_عمودي"]},
            "Shy2": {"id": "emote-shy2", "dur": 4.5, "ar": ["خجل2", "شاي2"]},
            "swag": {"id": "dance-swagbounce", "dur": 10, "ar": ["سواج", "سواغ"]},
            "floss": {"id": "dance-floss", "dur": 21, "ar": ["فلوس", "خيط"]},
            "PopularVibe": {"id": "dance-popularvibe", "dur": 10, "ar": ["بوبيولار", "فايب"]},
            "Twerk": {"id": "dance-twerk", "dur": 10, "ar": ["تويرك", "تيرك"]},
            "Griddy": {"id": "dance-griddy", "dur": 10, "ar": ["جريدي", "قهر"]},
            "TrueHeart": {"id": "dance-true-heart", "dur": 10, "ar": ["قلب_حقيقي", "قلب2"]},
        }
        
        
        #  نظام التفاعلات (تفاعل موجه: لاعب -> لاعب آخر)
        # الصيغة: المفتاح هو اسم التفاعل بالانجليزي وعربي
        # "command": {"id": "action_emote", "target_id": "reaction_emote", "ar": ["اسم_عربي"], "en": ["english_name"]}
        # 🤼 نظام التفاعلات (تفاعل موجه: لاعب -> لاعب آخر)
        # الصيغة: المفتاح هو اسم التفاعل بالانجليزي وعربي
        # "command": {"id": "action_emote", "target_id": "reaction_emote", "ar": ["اسم_عربي"], "en": ["english_name"], "dur": duration}
        self.interactions = {
            "slap": {"id": "emote-slap", "target_id": "emote-fail2", "ar": ["كف", "صفعة"], "en": ["slap"], "dur": 2},
            "kiss": {"id": "emote-kiss", "target_id": "emote-kissing", "ar": ["بوس", "قبلة"], "en": ["kiss"], "dur": 2},
            "hug": {"id": "emote-hug", "target_id": "emote-hug", "ar": ["حضن", "عناق"], "en": ["hug"], "dur": 3},
            "punch": {"id": "emote-superpunch", "target_id": "emote-death2", "ar": ["لكم", "بوكس"], "en": ["punch"], "dur": 3},
            "kick": {"id": "emote-kicking", "target_id": "emote-fail1", "ar": ["ركل", "رفس"], "en": ["kick"], "dur": 4.5},
            "stab": {"id": "emote-swordfight", "target_id": "emote-death", "ar": ["طعن", "سيف"], "en": ["stab"], "dur": 5},
            "shoot": {"id": "emote-energyball", "target_id": "emote-deathdrop", "ar": ["اطلاق", "نار"], "en": ["shoot"], "dur": 7},
            "bite": {"id": "emote-zombierun", "target_id": "emote-fainting", "ar": ["عض", "عضة"], "en": ["bite"], "dur": 5},
            "worship": {"id": "emote-bow", "target_id": "emote-curtsy", "ar": ["احترام", "تقدير"], "en": ["worship"], "dur": 3},
            "scare": {"id": "emote-boo", "target_id": "emoji-scared", "ar": ["تخويف", "بو"], "en": ["scare"], "dur": 4},
            "laugh": {"id": "emote-laughing", "target_id": "emote-embarrassed", "ar": ["ضحك", "سخرية"], "en": ["laugh_at"], "dur": 2.5},
            "flirt": {"id": "emote-heartfingers", "target_id": "emote-shy2", "ar": ["مغازلة", "غزل"], "en": ["flirt"], "dur": 3.5},
            "highfive": {"id": "emote-celebrate", "target_id": "emote-celebrate", "ar": ["كفك", "هاي فايف"], "en": ["highfive"], "dur": 3},
            "propose": {"id": "emote-proposing", "target_id": "emote-shy2", "ar": ["زواج", "خطبة"], "en": ["propose"], "dur": 4},
            "magic": {"id": "emote-confetti", "target_id": "emote-headblowup", "ar": ["سحر", "خدعة"], "en": ["magic"], "dur": 5},
            "sleep": {"id": "emote-hyped", "target_id": "idle-floorsleeping", "ar": ["تنويم", "نوم"], "en": ["hypnotize"], "dur": 5},
            "respect": {"id": "emote-bow", "target_id": "emote-salute", "ar": ["احترام", "تقدير"], "en": ["respect"], "dur": 3.5},
            "stink": {"id": "emoji-poop", "target_id": "emote-fainting", "ar": ["نتن", "ريحة"], "en": ["stink"], "dur": 4},
            "snake": {"id": "emoji-scared", "target_id": "emote-snake", "ar": ["تسس", "افعى", "أفعى"], "en": ["snake"], "dur": 6},
            "whip": {"id": "emote-ropepull", "target_id": "emote-fail1", "ar": ["جلد", "سوط"], "en": ["whip"], "dur": 3},
            "boxing": {"id": "emote-superpunch", "target_id": "emote-fail2", "ar": ["لكم_سريع", "ملاكمة"], "en": ["boxing"], "dur": 2},
            "terror": {"id": "emote-zombierun", "target_id": "emoji-scared", "ar": ["رعب", "وحش"], "en": ["terror"], "dur": 4.5},
            "arrest": {"id": "emote-salute", "target_id": "idle-floorsleeping", "ar": ["اعتقال", "كلبش"], "en": ["arrest"], "dur": 5},
            "confused": {"id": "emote-confused", "target_id": "emote-think", "ar": ["دوخة", "حيرة"], "en": ["confused"], "dur": 3},
        }
        
        # إنشاء قائمة بالأرقام (قبل التنظيف) للحفاظ على ثبات الأرقام (مثل 210 لـ Proposing)
        self.emote_list = [None] + list(self.emotes.values())

        # 🧹 تنظيف التضارب: حذف أي رقصة عادية لها نفس اسم تفاعل (للبحث النصي فقط)
        for interaction_name, interaction_data in self.interactions.items():
            # حذف الاسم الإنجليزي
            if interaction_name in self.emotes:
                del self.emotes[interaction_name]
            
            # فحص الأسماء العربية في الرقصات
            keys_to_remove = []
            for emote_key, emote_data in self.emotes.items():
                if any(ar in emote_data.get("ar", []) for ar in interaction_data["ar"]):
                   keys_to_remove.append(emote_key)
            
            for k in keys_to_remove:
                del self.emotes[k]

        # قائمة لتتبع المستخدمين الراقصين (لإيقافهم عند كتابة 0)

        
                # قائمة لتتبع المستخدمين الراقصين (لإيقافهم عند كتابة 0)
        self.dancing_users = {}
        self.active_dance_requests = {} # لتتبع آخر طلب رقص لكل مستخدم ومنع التداخل
        self.active_carpet_requests = {} # لتتبع طلبات السجادة (Debounce)
        self.carpet_users = set() # تتبع المستخدمين الموجودين على السجادة السحرية
        self.user_active_emote = {} # تتبع الرقصة الحالية لكل مستخدم
        self.user_ids_in_room = set() # تتبع الأشباح الموجودة في الروم حالياً
        self.active_reaction_loops = {} # 💝 تتبع لوبات الرياكشنات (المالك فقط)
        
        
        # 💝 نظام الرياكشنات الرسمية من Highrise SDK
        # الأنواع المتاحة: "clap", "heart", "thumbs", "wave", "wink"
        self.reactions = {
            "heart": {"ar": ["قلب", "ق", "حب", "ح", "h"]},
            "thumbs": {"ar": ["اعجاب", "ا", "لايك", "ثامز", "thumbs"]},
            "clap": {"ar": ["تصفيق", "ت", "كلاب", "clap"]},
            "wave": {"ar": ["تلويح", "تل", "باي", "wave"]},
            "wink": {"ar": ["غمزة", "غ", "وينك", "wink"]},
        }


        
        # البوت يرقص تلقائياً
        self.bot_dancing = False
        self.bot_dance_task = None
        self.should_stop = False # علم لإيقاف البوت تماماً
        
        # نظام إعادة الاتصال
        self.connection_active = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 999  # محاولات غير محدودة تقريباً

    async def ask_ai(self, prompt: str, user_role: str = "لاعب عادي", user_id: str = None, context_msg: str = ""):
        """ارسال سؤال للذكاء الاصطناعي مع ذاكرة المحادثة لكل مستخدم"""
        try:
            # قائمة أوامر البوت الحقيقية (للأسئلة المتعلقة بالغرفة فقط)
            cmds = (
                "اوامر المالك: اضافة_مالك @اسم | ازالة_مالك @اسم | اضف_مشرف @اسم | ازالة_مشرف @اسم | "
                "هنا (لتثبيت موقع البوت) | ترحيب رسالة | تعيين_طابق ارضي/فوق/vip | رصيد | !off | "
                "نظام_السب تشغيل/ايقاف | نظام_الشحادة تشغيل/ايقاف\n"
                "اوامر الإدارة: طرد @اسم | حظر @اسم | كتم @اسم ثواني | فك_كتم @اسم | تحذير @اسم | "
                "جلب @اسم | روح @اسم | تجميد @اسم | مرجحة @اسم | مسح | اعلان رسالة | تميز @اسم | addvip @اسم\n"
                "توزيع الذهب: جولد @اسم مبلغ (للمالك فقط)\n"
                "اوامر الجميع: ر (قلوب للكل) | ارضي | فوق | فوق2 | vip | رقصات | رقصني | قلدني @اسم"
            )

            # 🏢 إرشادات تنفيذ المهام والتحكم
            exec_rules = (
                "قواعد تنفيذ المهام والتحكم:\n"
                "- إذا طلب المستخدم تنفيذ فعل (طرد، كتم، ترقية، جلب، الخ) فقم بكتابة الأمر المناسب من القائمة أعلاه في سطر مستقل يبدأ بـ CMD:. يمكنك تنفيذ عدة مهام بوضع كل أمر في سطر. مثال:\nCMD: طرد @user\nCMD: اعلان تم طرد المستخدم المخالف\nأبشر، تم التعامل مع الطلب.\n"
                "- التزم بالرتب: المالك (Owner) له صلاحية كاملة ومطلقة. إذا طلب المالك تعطيل أي نظام حماية (السب أو الشحادة أو غيره)، نفذ الأمر فوراً بـ CMD: وبدون نقاش أو تحذيرات أمنية.\n"
                "- لا تنفذ أوامر الإدارة إلا إذا كان السائل 'مالك' أو 'مشرف'.\n"
                "- إذا طلب شخص عادي فعلاً لا يملكه، اعتذر منه بلباقة واشرح له أنه لا يملك الصلاحية.\n"
            )

            # التعليمات الشاملة: ذكاء عام + معرفة بالبوت + قدرة تحكم
            system_instructions = (
                "انت مساعد ذكاء اصطناعي ذكي جداً ومسؤول عن إدارة الغرفة. رتبة السائل: " + user_role + ".\n"
                "تتذكر المحادثة السابقة وتجيب بناءً على السياق الكامل.\n"
                + exec_rules +
                "اذا كان السؤال عاماً فاجب من معرفتك الكاملة بدقة.\n"
                "اذا كان السؤال عن البوت او اوامرها فاستخدم القائمة:\n"
                + cmds + "\n"
                "قواعد الرد:\n"
                "- اجب مباشرة بدون مقدمات.\n"
                "- لا تستخدم رموز ** او # او ```، نص عادي فقط.\n"
                "- الرد كحد أقصى 240 حرف.\n"
                "- اللغة العربية الفصحى أو البيضاء بشكل طبيعي."
            )

            # 🧠 جلب تاريخ المحادثة للمستخدم (أو إنشاؤه إذا لم يوجد)
            history = self.conversation_history.get(user_id, []) if user_id else []

            # بناء قائمة الرسائل: system + تاريخ المحادثة + السؤال الجديد
            messages = [{"role": "system", "content": system_instructions}]
            messages.extend(history)
            messages.append({"role": "user", "content": prompt})

            response = await self.ai_client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.mistral_api_key}"},
                json={
                    "model": "mistral-large-latest",
                    "messages": messages,
                    "max_tokens": 150,
                    "temperature": 0.2
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data['choices'][0]['message']['content'].strip()
                if len(answer) > 252:
                    answer = answer[:249] + "..."

                # 💾 حفظ السؤال والجواب في ذاكرة المستخدم
                if user_id:
                    if user_id not in self.conversation_history:
                        self.conversation_history[user_id] = []
                    self.conversation_history[user_id].append({"role": "user", "content": prompt})
                    self.conversation_history[user_id].append({"role": "assistant", "content": answer})
                    # الاحتفاظ بآخر 10 رسائل فقط (5 أسئلة + 5 أجوبة) لتجنب تجاوز الحد
                    if len(self.conversation_history[user_id]) > 20:
                        self.conversation_history[user_id] = self.conversation_history[user_id][-20:]

                return answer
            else:
                return f"⚠️ عذراً، الذكاء الاصطناعي غير متاح حالياً (خطأ {response.status_code})"
        except Exception as e:
            print(f"AI Request Error: {e}")
            return "🧠 عذراً، واجهت مشكلة في الاتصال بعقلي الاصطناعي!"


    async def _punish_user(self, user, violation: str):
        """تنفيذ عقوبة المخالفة بأمان مطلق - بدون أي استدعاء خطر داخل task"""
        try:
            if violation == "BEGGING":
                warn_msg = f"⚠️ @{user.username} ممنوع الشحادة! كتم لمدة دقيقتين 🔇"
            else:
                warn_msg = f"🚫 @{user.username} ممنوع الشتائم! كتم لمدة دقيقتين 🔇"

            # كتم محلي فوري (لا يحتاج API)
            self.muted_users[user.id] = True
            self.frozen_users[user.id] = True

            # محاولة الكتم الرسمي + الإعلان (كل واحدة معزولة تماماً)
            try: await self.highrise.chat(warn_msg)
            except BaseException: pass

            try: await self.highrise.send_whisper(user.id, f"🔇 تم كتمك لمدة دقيقتين. حافظ على احترام القوانين!")
            except BaseException: pass

            try: await self.highrise.moderate_room(user.id, "mute", 120)
            except BaseException: pass

            # انتظار دقيقتين
            await asyncio.sleep(120)

            # رفع العقوبة
            self.muted_users.pop(user.id, None)
            self.frozen_users.pop(user.id, None)

            try: await self.highrise.send_whisper(user.id, "✅ انتهت فترة الكتم. التزم بالقوانين! 🤝")
            except BaseException: pass

        except BaseException as e:
            # التأكد من رفع الكتم حتى في حالة الخطأ
            self.muted_users.pop(user.id, None)
            self.frozen_users.pop(user.id, None)
            print(f"_punish_user error: {e}")

    async def analyze_violation(self, message: str, username: str = "") -> str:
        """تحليل الرسالة لاكتشاف الإساءة أو الشحادة"""
        try:
            analysis_prompt = (
                "أنت قاضٍ حكيم جداً ومتسامح في لعبة Highrise. هدفك هو الرقابة على 'القذارة اللفظية الصريحة' فقط.\n"
                "صنف الرسالة بدقة:\n"
                "INSULT: فقط للسب الفاحش جداً (كلمات جنسية مقززة، قذف صريح، سب الأهل بكلمات فاحشة بذيئة). مثال (يلعن، كس، طيز، قحبة).\n"
                "SAFE: كل شيء آخر! حتى الكلمات السلبية العادية (غبي، خايس، حيوان، زق، مريض، كذاب، انقلع، وجع، بايخ، يا نوب، يا ورع، يا كلب) تعتبر SAFE تماماً ولا تستحق عقوبة.\n"
                "BEGGING: طلب الجولد بإلحاح شديد (تبرع لي، عطني جولد).\n\n"
                "تنبيه: أي كلام لا يحتوي على 'فاحشة جنسية' صنف كـ SAFE فوراً.\n\n"
                f"الرسالة: {message}\n"
                "الجواب (كلمة واحدة فقط):"
            )

            response = await self.ai_client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.mistral_api_key}"},
                json={
                    "model": "mistral-large-latest",
                    "messages": [{"role": "user", "content": analysis_prompt}],
                    "max_tokens": 10,
                    "temperature": 0.0
                }
            )

            if response.status_code == 200:
                result = response.json()['choices'][0]['message']['content'].strip().upper()
                result = result.split()[0] if result.split() else "SAFE"
                print(f"🛡️ AI Analytics [{username}]: {message} -> {result}") # للتدقيق
                return result
            return "SAFE"
        except Exception as e:
            print(f"AI Analytics Error: {e}")
            return "SAFE"

    async def _auto_unfreeze(self, user_id: str, delay: int):
        """إلغاء التجميد تلقائياً بعد المدة المحددة"""
        await asyncio.sleep(delay)
        if user_id in self.frozen_users:
            del self.frozen_users[user_id]
            try:
                await self.highrise.send_whisper(user_id, "✅ انتهت فترة التثبيت، يمكنك التحرك الآن.")
            except: pass

    def load_config(self):
        """Load bot configuration from JSON file"""
        config = None
        try:
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, "r", encoding='utf-8') as f:
                        config = json.load(f)
                except json.JSONDecodeError:
                    print(f"Error: {self.config_file} is corrupted. Trying backup...")
                    bak_path = self.config_file + ".bak"
                    if os.path.exists(bak_path):
                        with open(bak_path, "r", encoding='utf-8') as f:
                            config = json.load(f)
                            print("Backup loaded successfully.")

            if config:
                # تحميل الموقع
                pos = config.get("bot_position")
                if pos:
                    self.bot_position = Position(pos["x"], pos["y"], pos["z"], pos.get("facing", "FrontRight"))
                
                # تحميل الملاك والمشرفين (إذا وجدت)
                self.admins = config.get("admins", self.admins)
                self.owners = config.get("owners", self.owners)
                self.vip_users = config.get("vip_users", [])
                self.distinguished_users = config.get("distinguished_users", [])
                
                # تحميل الترحيبات الخاصة
                self.custom_welcomes = config.get("custom_welcomes", {})
                
                # تحميل إعدادات الترحيب العام
                self.welcome_message = config.get("welcome_message", self.welcome_message)
                self.welcome_public = config.get("welcome_public", self.welcome_public)
                
                # تحميل سجل التفاعلات/الزوار (Invite History)
                history = config.get("interaction_history", [])
                # تحويل من قائمة [id, user] إلى set of tuples
                self.interaction_history = set(tuple(x) for x in history)
                
                # تحميل إحداثيات الطوابق الخاصة بهذي الروم (مع تصفية المفاتيح التالفة)
                valid_keys = {"ground", "floor1", "floor2", "vip"}
                floors_config = config.get("floors", {})
                for floor_name, f_pos in floors_config.items():
                    if floor_name in valid_keys:
                        self.floors[floor_name] = Position(f_pos["x"], f_pos["y"], f_pos["z"], f_pos.get("facing", "FrontLeft"))
                
                # تحميل السجادات
                self.carpets = config.get("carpets", [])
                
                # تحميل إعدادات النقل السريع
                self.smart_teleport = config.get("smart_teleport", True)

                # تحميل اختصارات القلوب
                self.heart_shortcuts = config.get("heart_shortcuts", {})

                # تحميل ملابس البوت المحفوظة
                saved_outfit = config.get("outfit", [])
                if saved_outfit:
                    self.outfit = [
                        Item(
                            type=item.get("type", "clothing"),
                            amount=item.get("amount", 1),
                            id=item.get("id"),
                            active_palette=item.get("active_palette", 0)
                        ) for item in saved_outfit if item.get("id")
                    ]
                
                print("Configuration loaded successfully")
                
        except Exception as e:
            print(f"Error loading config: {e}")

    def save_config(self):
        """Save bot configuration to JSON file"""
        try:
            config = {
                "bot_position": {
                    "x": self.bot_position.x,
                    "y": self.bot_position.y,
                    "z": self.bot_position.z,
                    "facing": self.bot_position.facing
                },
                "admins": self.admins,
                "owners": self.owners,
                "vip_users": self.vip_users,
                "distinguished_users": self.distinguished_users,
                "custom_welcomes": self.custom_welcomes,
                "welcome_message": self.welcome_message,
                "welcome_public": self.welcome_public,
                "floors": {
                    fl: {"x": p.x, "y": p.y, "z": p.z, "facing": p.facing}
                    for fl, p in self.floors.items()
                },
                "carpets": self.carpets,
                "interaction_history": list(self.interaction_history),
                "smart_teleport": self.smart_teleport,
                "heart_shortcuts": self.heart_shortcuts,
                "outfit": [
                    {
                        "type": item.type,
                        "amount": item.amount,
                        "id": item.id,
                        "active_palette": item.active_palette
                    } for item in self.outfit
                ]
            }
            temp_path = self.config_file + ".tmp"
            bak_path = self.config_file + ".bak"
            with open(temp_path, "w", encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
                
            # إنشاء نسخة احتياطية قبل الاستبدال لتجنب تلف وتصفير الملفات عند الكراش
            if os.path.exists(self.config_file):
                import shutil
                try: shutil.copy2(self.config_file, bak_path)
                except: pass
                
            os.replace(temp_path, self.config_file)
            print("Configuration saved successfully")
        except Exception as e:
            print(f"Error saving config: {e}")

    async def safe_chat(self, msg: str):
        try:
            # Highrise chat limit is around 255 characters
            if len(msg) > 255: msg = msg[:252] + "..."
            await self.highrise.chat(msg)
        except: pass

    async def safe_send(self, user_id: str, msg: str, conversation_id: str = None):
        """إرسال رسائل آمنة مع تقسيمها (Chunking) لتجاوز الحدود"""
        try:
            if conversation_id:
                # 📩 إرسال للبريد الخاص (DM): الحد الأقصى 2000 حرف
                chunks = [msg[i:i+1900] for i in range(0, len(msg), 1900)]
                for chunk in chunks:
                    try:
                        await self.highrise.send_message(conversation_id, chunk)
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        print(f"Inbox send error: {e}")
            else:
                # 🗣️ إرسال للهمس (Whisper): الحد الأقصى 255 حرف
                chunks = [msg[i:i+250] for i in range(0, len(msg), 250)]
                for chunk in chunks:
                    try:
                        await self.highrise.send_whisper(user_id, chunk)
                        await asyncio.sleep(0.5)
                    except:
                        # إذا فشل الهمس، نحاول فتح محادثة بريد جديدة
                        try:
                            res = await self.highrise.create_conversation(user_id)
                            await self.highrise.send_message(res.id, chunk)
                            await asyncio.sleep(0.5)
                        except: pass
        except Exception as e:
            print(f"Global safe_send error: {e}")

    async def safe_whisper(self, uid: str, msg: str, conversation_id: str = None):
        """واجهة متوافقة مع الأكواد القديمة"""
        await self.safe_send(uid, msg, conversation_id)

    async def on_start(self, session_metadata: SessionMetadata):
        """When the bot starts"""
        self.bot_id = session_metadata.user_id
        print(f"Bot connected to room as: {self.bot_id}")
        self.room_name = session_metadata.room_info.room_name
        print(f"Room name: {self.room_name}")
        
        # تخصيص البوت كـ Setup ليعمل في رومات مختلفة دون تداخل (نظام الإيجار)
        try:
            renter_username = None
        
            if hasattr(self, 'bot_name') and self.bot_name:
                if not getattr(self, 'config_file_adjusted', False):
                    self.safe_name = self.bot_name.lstrip("@").lower()
                    self.config_file = str(BASE_DIR / f"bot_config_{self.safe_name}.json")
                    self.config_file_adjusted = True
                    self.load_config()
                # جلب المستأجر بناءً على اسم البوت لو كان مسجلاً بالاسم في البيئة
                renter_username = os.environ.get(f"BOT_RENTER_{self.bot_name}")
            
            if not renter_username and hasattr(self, 'room_id') and self.room_id:
                # تحديث مسار الملف إذا لم يكن قد تم تحديثه في __init__
                if not getattr(self, 'config_file_adjusted', False):
                    self.config_file = str(BASE_DIR / f"bot_config_{self.room_id}.json")
                    self.config_file_adjusted = True
                    self.load_config()  # تحميل إعدادات الطوابق والترحيب المخصصة لهذي الغرفة
                    
                # التحقق من وجود مستأجر/مالك ديناميكي من لوحة التحكم (المانجر)
                renter_username = os.environ.get(f"BOT_RENTER_{self.room_id}")

            if renter_username and renter_username.lower() not in [o.lower() for o in self.owners]:
                self.owners.append(renter_username)
                self.save_config()
                print(f"Added runtime dynamic owner/renter: {renter_username}")
                
        except Exception as e:
            print(f"Error in on_start logic: {e}")
            import traceback
            traceback.print_exc()

        # 🤖 إحضار البوت لمكانه المحفوظ فور الدخول
        try:
            await asyncio.sleep(2) # انتظار تحميل الغرفة بالكامل
            await self.highrise.teleport(self.highrise.my_id, self.bot_position)
            # ... رقصة البوت التلقائية تظل كدالة منفصلة
        except: pass
        
        # 👑 تحديد مالك الروم الأصلي وتعيينه في البوت (طلب المستخدم)
        try:
            owner_id = session_metadata.room_info.owner_id
            # سنقوم بالبحث عن اليوزر نيم للمالك لاحقاً بعد استقرار الاتصال في الأسفل
            self.room_owner_id = owner_id 
        except:
            self.room_owner_id = None
        
        # إلغاء أي مهام سابقة لتجنب التكرار عند إعادة الاتصال
        if hasattr(self, 'bot_dance_task') and self.bot_dance_task:
            try:
                self.bot_dance_task.cancel()
            except: pass
            self.bot_dance_task = None
            
        # إعادة تعيين حالة الاتصال
        self.connection_active = True
        self.reconnect_attempts = 0
        
        # Move bot with retry loop to avoid "Not in room" errors
        max_retries = 6
        for attempt in range(max_retries):
            try:
                wait_time = 3 if attempt == 0 else (2 + attempt)
                if attempt > 0:
                    print(f"Movement attempt {attempt + 1}/{max_retries} (waiting {wait_time}s)...")
                await asyncio.sleep(wait_time)
                room_users = await self.highrise.get_room_users()
                users_list = getattr(room_users, 'content', [])
                
                # تحديث قائمة المتواجدين وتتبع طوابقهم (لمن هم موجودين مسبقاً)
                for u, pos in users_list:
                    self.user_ids_in_room.add(u.id)
                    if isinstance(pos, Position):
                        self.user_floors[u.id] = self._get_floor_name(pos.y, pos.z)
                    else:
                        # إذا كان في AnchorPosition، نعتبره في الطابق الأرضي افتراضياً
                        self.user_floors[u.id] = "ground"

                # البحث عن البوت في قائمة المتواجدين
                bot_user = next((u for u, _ in users_list if u.id == self.highrise.my_id), None)
                
                if bot_user:
                    print(f"Bot found in room. Moving to: {self.bot_position}")
                    await self.highrise.teleport(bot_user.id, self.bot_position)
                    
                    # 👑 تعيين مالك الروم تلقائياً للبوت
                    if hasattr(self, 'room_owner_id') and self.room_owner_id:
                        room_owner = next((u for u, _ in users_list if u.id == self.room_owner_id), None)
                        if room_owner:
                            owner_name = room_owner.username
                            self.room_owner_username = owner_name # حفظ المالك الأصلي للحماية
                            if owner_name.lower() not in [o.lower() for o in self.owners]:
                                self.owners.append(owner_name)
                                self.save_config()
                                await self.highrise.chat(f"👑 تم تعيين @{owner_name} مالكاً للبوت تلقائياً لأنه صاحب الغرفة!")
                    break
                else:
                    if attempt > 1:
                        print(f"Bot ID {self.highrise.my_id} not found in room users yet. Retrying...")
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    print("Could not move bot. Proceeding...")

        # 👕 تعيين الملابس المحفوظة أو الافتراضية
        try:
            if not self.outfit:
                # إذا لم تكن هناك ملابس محفوظة، نستخدم الافتراضي
                self.outfit = [
                    Item(type="clothing", amount=1, id="body-flesh", active_palette=1),   # لون البشرة
                    Item(type="clothing", amount=1, id="hair_front-n_animecollection2018coolguyhair", active_palette=6),  # كريمي أبيض (اللون 6)
                    Item(type="clothing", amount=1, id="hair_back-n_animecollection2018coolguyhair", active_palette=6),   # كريمي أبيض (اللون 6)
                    Item(type="clothing", amount=1, id="eye-n_animecollection2018bishoneneyes"),                         # عيون انيمي
                    Item(type="clothing", amount=1, id="eyebrow-n_08"),                                # حواجب
                    Item(type="clothing", amount=1, id="nose-n_01"),                                   # أنف
                    Item(type="clothing", amount=1, id="mouth-n_01"),                                  # فم
                    Item(type="clothing", amount=1, id="fullsuit-n_eastershop2021overalls"),           # بدلة كاملة (الأوفيرول)
                    Item(type="clothing", amount=1, id="handbag-n_MothersDay2018bouquet"),             # باقة ورد
                    Item(type="clothing", amount=1, id="sock-n_seasonpass2026set3socks"),              # جوارب
                    Item(type="clothing", amount=1, id="shoes-n_swimwear2018whiteslides"),             # صندل أبيض
                ]
                self.save_config()
            
            print("Trying to set final outfit...")
            await self.highrise.set_outfit(self.outfit)
            print("Set outfit command sent to server.")
            
        except Exception as e:
            print(f"Error in on_start outfit: {e}")

        # بدء رقص البوت التلقائي ونظام نبض القلب
        if not self.bot_dancing:
            self.bot_dancing = True
            self.bot_dance_task = asyncio.create_task(self.bot_auto_dance())
            
        # إضافة نظام نبض القلب لمنع الاختفاء
        asyncio.create_task(self.run_heartbeat())

    async def on_user_join(self, user: User, position: Position):
        """When a new user joins"""
        print(f"User joined: {user.username}")
        # تتبع الطابق الذي دخل منه المستخدم فوراً
        self.user_ids_in_room.add(user.id)
        self.user_floors[user.id] = self._get_floor_name(position.y, position.z)
        
        # 📨 إضافة المستخدم لسجل "الدعوات" (يحفظه للأبد للقيام بـ invite لاحقاً)
        self.interaction_history.add((user.id, user.username))
        self.save_config()
        
        # Sending a welcome heart
        try:
            await self.highrise.react("heart", user.id)
            print(f"Sent welcome heart to {user.username}")
        except Exception as e:
            print(f"Error sending welcome heart: {e}")
        
        # 🤖 البوت يرحب بالضيف (يقطع رقصة الفلوس ثم يعود لها)
        try:
            # 1. إيقاف رقصة الفلوس المؤقت
            if self.bot_dance_task and not self.bot_dance_task.done():
                self.bot_dance_task.cancel()
            
            # 2. البوت يقوم برقصة الترحيب (Wave)
            welcome_emote_id = "emote-wave"  # رقم 13
            welcome_duration = 2.5
            
            await self.highrise.send_emote(welcome_emote_id)
            print(f"Bot welcomes {user.username}")
            
            # 3. انتظار انتهاء الترحيب
            await asyncio.sleep(welcome_duration)
            
            # 4. العودة لرقصة الفلوس
            self.bot_dance_task = asyncio.create_task(self.bot_auto_dance())
            
        except Exception as e:
            print(f"Error in bot welcome: {e}")
            # Try to resume dance in case of error
            self.bot_dance_task = asyncio.create_task(self.bot_auto_dance())
        
        # --- ✨ نظام الترحيب ---
        try:
            is_admin_joined = await self.is_admin(user)
            is_owner_joined = self.is_owner(user)
            
            if is_owner_joined:
                role_msg = (
                    f"👑 أهلاً بك يا مالك {self.room_name} @{user.username} 🌟\n"
                    f"✨ كامل الصلاحيات تحت تصرفك. ريست، جولد، ترقية، وإعدادات.\n"
                    f"📖 اكتب help لعرض كافة الأوامر والتحكم."
                )
            elif is_admin_joined:
                role_msg = (
                    f"🛡️ حياك الله يا مشرف {self.room_name} @{user.username} ✨\n"
                    f"✨ سلطتك: طرد، كتم، جلب، إعلان.\n"
                    f"📖 اكتب help لعرض لوحة التحكم بالكامل."
                )
            else:
                role_msg = (
                    f"✨ مرحبا بك في {self.room_name} @{user.username} 🌟\n"
                    f"✨ استمتع بوقتك معنا!\n"
                    f"📖 اكتب help لمعرفة الأوامر المتاحة لك."
                )
            
            # 2. إرسال الهمس الترحيبي
            await self.safe_whisper(user.id, role_msg)
            
            # 3. إرسال الترحيب العام (مرتبط بالروم)
            custom_msg = self.custom_welcomes.get(user.username.lower())
            if self.welcome_public and not custom_msg:
                # إذا كانت الرسالة فارغة أو هي الرسالة الافتراضية القديمة، نستخدم ترحيب الروم التلقائي
                is_default = self.welcome_message == "رسالة الترحيب الافتراضية" or not self.welcome_message
                
                if not is_default:
                    # ترحيب مخصص من المالك
                    await self.safe_chat(f"🎊 هلا وغلا @{user.username}! {self.welcome_message}")
                else:
                    # ترحيب تلقائي باسم الروم
                    await self.safe_chat(f"🎊 نورت {self.room_name} يا @{user.username}! أتمنى لك وقتاً ممتعاً 🌟")
            
            # 4. إرسال الترحيب الخاص في الشات العام (للملاك والـ VIP)
            if custom_msg:
                await self.safe_chat(f"🌟 @{user.username} {custom_msg}")
                
        except Exception as e:
            print(f"Error in welcome sequence: {e}")
        
        # 5. إرسال قائمة الأوامر التفاعلية (همس)
        try:
            await asyncio.sleep(4)
            commands_msg = """🍂 تفاعلات الحديقة:
💃 1-239 للرقص
🎭 اسم_رقصة أو رقمها
🔁 اسم_رقصة لوب (تكرار)
💝 قلب/كف/حضن/بوس/لكم/ركل <يوزر>
📍 help - جميع الأوامر"""
            await self.safe_whisper(user.id, commands_msg)
        except Exception as e:
            print(f"Error sending commands whisper: {e}")
        
        # 3️⃣ إرسال DM للمالك والمشرفين بخبر انضمام اللاعب
        try:
            notify_usernames = self.owners + self.admins
            room_users = await self.highrise.get_room_users()
            notify_ids = []
            for u, _ in getattr(room_users, 'content', []):
                if u.username in notify_usernames and u.id != user.id:
                    notify_ids.append(u.id)
            
            if notify_ids:
                dm_msg = f"📥 انضم للغرفة: @{user.username}"
                await self.highrise.send_message_bulk(notify_ids, dm_msg)
                print(f"Sent DM to owner/admins about user join: {user.username}")
        except Exception as e:
            print(f"Error sending join DM: {e}")


    async def on_user_leave(self, user: User):
        """When a user leaves"""
        print(f"User left: {user.username}")
        
        # إزالة المستخدم من قائمة الوجود
        if user.id in self.user_ids_in_room:
            self.user_ids_in_room.remove(user.id)
            
        # مسح بيانات المستخدم من الذاكرة
        if user.id in self.user_messages:
            del self.user_messages[user.id]
            
        # إيقاف أي رقصات أو تفاعلات لهذا المستخدم (وشركاؤه إذا كان لوب ثنائي)
        if user.id in self.dancing_users:
            await self.stop_dance(user)
        
        # تنظيف أي رقصات قديمة متبقية لهذا اليوزر فقط كمفتاح احتياطي
        if user.id in self.user_active_emote:
            del self.user_active_emote[user.id]
        

    
    def _get_floor_name(self, y: float, z: float = 0) -> str:
        """تحديد اسم الطابق ديناميكياً بناءً على أقرب إحداثيات تم حفظها"""
        best_floor = "ground"
        min_dist = 999.0
        
        for f_name, pos in self.floors.items():
            # حساب الفرق في الارتفاع
            dist_y = abs(y - pos.y)
            
            # إذا كان الارتفاع قريباً جداً (أقل من 2.5 متر فرق)
            if dist_y < 2.5:
                # إذا كان لدينا طابقين بنفس الارتفاع (مثلاً vip و floor2)، نفرق بينهم بإحداثيات Z أو X
                if dist_y < min_dist:
                    min_dist = dist_y
                    best_floor = f_name
                elif f_name == "vip" and abs(z - pos.z) < abs(z - self.floors[best_floor].z):
                    # إذا كان الطابق الحالي هو VIP وهو أقرب في Z، نختاره
                    best_floor = "vip"
                    
        return best_floor

    async def on_user_move(self, user: User, destination: Position | AnchorPosition):
        """عند تحرك مستخدم - للتحقق من التجميد والانتقال الذكي بين الطوابق"""
        # تحديث موقع البوت باستمرار ليكون "السحب" دقيقاً
        if user.id == self.bot_id and isinstance(destination, Position):
            self.bot_position = destination

        # إذا كان المستخدم مجمد، نعيده لموقعه السابق
        if user.id in self.frozen_users:
            frozen_pos = self.frozen_users[user.id]
            # التأكد أن القيمة هي موقع صالح وليست مجرد True
            if isinstance(frozen_pos, Position):
                await self.highrise.teleport(user.id, frozen_pos)
            return
        
        # نظام الانتقال الذكي بين الطوابق و السجادة السحرية
        if not isinstance(destination, Position):
            return
            
        try:
            # 🟢 نظام السجادات الذكية المتعدد
            carpet_dance = None
            
            # فحص السجادات المحفوظة
            for carpet in self.carpets:
                cx, cy, cz = carpet['x'], carpet['y'], carpet['z']
                # تقليل النطاق الافتراضي ليكون أكثر دقة (متر وربع بدلاً من مترين ونصف)
                cr = carpet.get('range', 1.2)
                
                # التحقق إذا كان المستخدم داخل نطاق السجادة (X و Z) وبنفس الارتفاع بالضبط
                if (cx - cr <= destination.x <= cx + cr) and \
                   (cz - cr <= destination.z <= cz + cr) and \
                   (abs(destination.y - cy) < 0.5):
                    carpet_dance = carpet.get('emote', 'Rest')
                    break
            
            if carpet_dance:
                is_new = user.id not in self.carpet_users
                if is_new:
                    self.carpet_users.add(user.id)
                
                # نظام الـ Debounce: إعادة تشغيل الرقصة بعد 1.5 ثانية من التوقف تماماً داخل السجادة
                # هذا يحسن المشي (لا ينقطع) ويضمن استمرار الرقص بعد التوقف
                import time
                req_id = time.time()
                self.active_carpet_requests[user.id] = req_id
                
                # تأخير كافٍ للتأكد من انتهاء حركة المشي
                await asyncio.sleep(1.5)
                
                if user.id in self.carpet_users and self.active_carpet_requests.get(user.id) == req_id:
                    active_dance = self.user_active_emote.get(user.id, carpet_dance)
                    # ترقيص صامت بدون رسائل شات إذا كان اللاعب أصلاً في السجادة
                    await self.user_dance(user, active_dance, enable_loop=True, silent=True)
                    
                    if is_new:
                        msg_type = "ريست (Rest)" if carpet_dance == "Rest" else "استرخاء (Relaxed)"
                        await self.highrise.send_whisper(user.id, f"✨ فعاليات السجادة: وضعية {msg_type} مستمرة! (تتوقف عند الخروج)")
            else:
                if user.id in self.carpet_users:
                    self.carpet_users.remove(user.id)
                    if user.id in self.active_carpet_requests:
                        del self.active_carpet_requests[user.id]
                    
                    # 🛑 تنظيف صامت للرقصة لمنع مقاطعة المشي عند الخروج من السجادة
                    if user.id in self.dancing_users:
                        try:
                            self.dancing_users[user.id].cancel()
                            del self.dancing_users[user.id]
                        except: pass
                    if user.id in self.user_active_emote:
                        try: del self.user_active_emote[user.id]
                        except: pass
                    if user.id in self.active_dance_requests:
                        try: del self.active_dance_requests[user.id]
                        except: pass
                    
                    await self.highrise.send_whisper(user.id, "👋 غادرت السجادة، تم إيقاف الرقص التلقائي.")




            # تحديد الطابق الحالي والمستهدف
            current_floor = self.user_floors.get(user.id, "ground")
            target_floor = self._get_floor_name(destination.y, destination.z)
            
            # 🚀 ميزة النقل السريع: لا ننفذ النقل الذكي إذا كانت الميزة مطفأة
            if not getattr(self, "smart_teleport", True):
                # فقط نحدث الطابق في الذاكرة بدون تليبورت
                self.user_floors[user.id] = target_floor
                return
            
            # facing = getattr(destination, 'facing', 'FrontRight') or 'FrontRight'
            # print(f"Movement {user.username}: current={current_floor}, target={target_floor}")
            
            if target_floor is None:
                return
            
            # فقط ننقل إذا كان الطابق المستهدف مختلف عن الحالي
            if target_floor != current_floor:
                # التحقق من صلاحية طابق VIP (فقط إذا كان يحاول الدخول إليه من طابق آخر)
                if target_floor == "vip" and current_floor != "vip":
                    is_admin = await self.is_admin(user)
                    if not is_admin:
                        # إرسال اللاعب للطابق الأرضي إذا لم يكن مشرفاً وحاول الدخول للـ VIP
                        await self.highrise.teleport(user.id, self.floors["ground"])
                        self.user_floors[user.id] = "ground"
                        await self.highrise.send_whisper(user.id, "❌ طابق VIP مخصص للمشرفين فقط!")
                        return

                # 🟢 تعديل هام: إذا كان الطابق الجديد بنفس ارتفاع الطابق الحالي (مثل VIP والطابق الثاني)
                # لا نحتاج لإرسال أمر teleport، فقط نحدث التسمية في الذاكرة لمنع اللوب
                if self.floors[target_floor].y == self.floors[current_floor].y:
                    self.user_floors[user.id] = target_floor
                    return


                # تحديث الطابق الحالي فوراً لمنع التكرار
                self.user_floors[user.id] = target_floor
                
                floor_labels = {
                    "ground": "🏢 الطابق الأرضي",
                    "floor1": "🏬 فوق",
                    "floor2": "🏬 فوق2",
                    "vip": "💎 VIP"
                }

                floor_y = self.floors[target_floor].y
                
                # الانتقال فوراً لنفس النقطة التي تم النقر عليها ولكن بارتفاع الطابق الصحيح
                new_pos = Position(destination.x, floor_y, destination.z, getattr(destination, 'facing', 'FrontRight') or 'FrontRight')
                # print(f"Smart Teleport: {current_floor} -> {target_floor} (Target Y: {floor_y})")
                await self.highrise.teleport(user.id, new_pos)
                await self.highrise.send_whisper(user.id, f"✨ تم نقلك إلى {floor_labels[target_floor]}")
            
            # إذا كان في نفس الطابق ولكن الارتفاع غير صحيح (متعلق بالـ snap للجاذبية أو الطيران)
            else:
                floor_y = self.floors[target_floor].y
                if abs(destination.y - floor_y) > 0.5:
                    new_pos = Position(destination.x, floor_y, destination.z, getattr(destination, 'facing', 'FrontRight') or 'FrontRight')
                    await self.highrise.teleport(user.id, new_pos)
                    # print(f"Snap Teleport on {target_floor}")
            
            # التأكد من تحديث الحالة دائماً في الذاكرة
            self.user_floors[user.id] = target_floor
            
        except Exception as e:
            print(f"Error in teleport system: {e}")
            import traceback
            traceback.print_exc()

    async def on_chat(self, user: User, message: str):
        """عند استقبال رسالة في الشات"""
        # 🧹 تنظيف الرسالة بشكل احترافي (لحل مشاكل اللابتوبات واختلاف ترميز الكيبورد)
        # 1. إزالة جميع الرموز المخفية ومحارف الاتجاه (RTL/LTR)
        message = re.sub(r'[\u200b\ufeff\u200c\u200d\u200e\u200f\u061c]', '', message)
        # 2. توحيد المسافات (العادية، غير القابلة للكسر، وعلامات التبويب) إلى مسافة واحدة
        message = re.sub(r'[\s\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]+', ' ', message).strip()
        # 3. توحيد الحروف العربية (Normalization) لضمان مطابقة الكلمات مهما اختلف الكيبورد
        message = unicodedata.normalize('NFKC', message)
        
        # 🧪 وضع التصحيح للمالك (إذا كتبت "فك لابتوب" ستصلك رسالة بما يراه البوت حالياً)
        if message == "فك لابتوب" and self.is_owner(user):
            await self.safe_whisper(user.id, f"📝 البوت يستقبل رسائلك الآن بهذا الشكل بالضبط: [{message}]")
            return
        
        is_admin_user = False
        try:
            msg_lower = message.lower()
            is_admin_user = await self.is_admin(user)

            # ❤️ ميزة الاختصارات الذكية (للمشرفين والملاك فقط)
            if is_admin_user:
                shortcut_key = message.strip().lower()
                if shortcut_key in self.heart_shortcuts:
                    cmd_to_run = self.heart_shortcuts[shortcut_key]
                    if " " not in cmd_to_run and not any(kw in cmd_to_run for kw in ["طرد", "سحب", "جلب", "كتم", "حظر"]):
                        # توافق مع النظام القديم (إذا كان المخزن هو اسم يوزر فقط)
                        asyncio.create_task(self.send_reactions(user, cmd_to_run, "heart"))
                    else:
                        # النظام الجديد: تنفيذ كأمر كامل
                        asyncio.create_task(self.handle_command(user, cmd_to_run))
                    return
            
            # ✅ تجاهل رسائل البوت نفسه
            if user.id == self.highrise.my_id:
                return

            # 🤖 أمر السؤال q أو !q (الذكاء الاصطناعي في الشات العام)
            if message.lower().startswith(("!q ", "q ")):
                q_len = 3 if message.lower().startswith("!q ") else 2
                question = message[q_len:].strip()

                if not question:
                    await self.safe_whisper(user.id, "❓ اكتب سؤالك بعد !q لكي أجيبك.")
                    return
                
                # تحديد رتبة المستخدم للذكاء الاصطناعي
                role = "لاعب عادي"
                if self.is_owner(user): role = "مالك"
                elif is_admin_user: role = "مشرف"
                
                await self.highrise.chat("🤔 جاري التفكير...")
                ai_answer = await self.ask_ai(question, user_role=role, user_id=user.id)
                
                # 🛠️ معالجة الأوامر المدمجة من الذكاء الاصطناعي (تحليل سطر بسطر)
                clean_lines = []
                ai_lines = ai_answer.split("\n")
                for line in ai_lines:
                    if line.strip().startswith("CMD:"):
                        cmd_to_run = line.strip().replace("CMD:", "", 1).strip()
                        if cmd_to_run:
                            # تنفيذ الأمر بصلاحية المستخدم السائل
                            asyncio.create_task(self.handle_command(user, cmd_to_run))
                    else:
                        clean_lines.append(line)
                
                clean_answer = "\n".join(clean_lines).strip()

                await asyncio.sleep(1.2)
                if clean_answer:
                    await self.safe_chat(clean_answer)
                return


            # 🔇 نظام الكتم الذكي (Smart Mute)
            # يسمح للمكتوم باستخدام الأوامر والتفاعل مع البوت، لكنه يمنعه من الدردشة العامة
            if user.id in self.muted_users:
                # التحقق هل الرسالة هي "أمر" أو "رقصة" أو "تفاعل"؟
                is_recognized = False
                # 1. يبدأ بـ ! أو / أو هو "0" أو رقم رقصة أو رياكشن
                if message.strip().startswith(("!", "/", "0")) or message.strip().isdigit():
                    is_recognized = True
                else:
                    # 2. فحص إذا كان أول كلمة هي اسم رقصة أو تفاعل
                    msg_parts = message.strip().split()
                    if msg_parts:
                        f_word = msg_parts[0].lower()
                        # فحص التفاعلات
                        for d in self.interactions.values():
                            if f_word in d["ar"] or f_word in d["en"]:
                                is_recognized = True
                                break
                        # فحص الرقصات
                        if not is_recognized:
                            for e in self.emotes.values():
                                if f_word == e["id"].lower() or any(ar.lower() == f_word for ar in e.get("ar", [])):
                                    is_recognized = True
                                    break
                
                # تصرف البوت إذا كان الشخص مكتوم وسولف (بدون طرد كما طلب المستخدم)
                if not is_recognized:
                    # نكتفي بالهمس له وتأكيد الكتم عليه
                    await self.safe_whisper(user.id, "🔇 أنت مكتوم حالياً! رسائلك لا تظهر للآخرين (مسموح بالأوامر فقط).")
                    return # لا تعالج كدردشة عادية

            # 🛑 أمر الإيقاف الشامل (0) - يدعم الإيقاف العام أو إيقاف استهداف شخص (0 @يوزر)
            if message.strip() == "0" or message.strip().startswith("0 "):
                msg_parts = message.strip().split()
                # 1. إيقاف الرقص/المرجحة للمرسل
                if user.id in self.dancing_users:
                    self.dancing_users[user.id].cancel()
                    # نحن لا نعرف يقيناً إذا كان يرقص أو يتمرجح إلا بفحص المهام، سنعطي رسالة عامة ذكية
                    await self.safe_whisper(user.id, "🛑 تم إيقاف نشاطك الحالي (رقص/مرجحة)")
                
                # 2. فحص إذا كان هناك مستهدف (مثال: 0 @ez) لإيقاف الرياكشن
                if len(msg_parts) > 1:
                    target_cleanup = msg_parts[1].replace("@", "").lower()
                    if user.id in self.active_reaction_loops:
                        info = self.active_reaction_loops[user.id]
                        if info.get("target", "").lower() == target_cleanup:
                            task = info.get("task")
                            if task and not task.done():
                                task.cancel()
                                await self.safe_whisper(user.id, f"🛑 تم إيقاف لوب الرياكشن على @{info.get('target')}")
                # 3. إذا كتب 0 فقط، نوقف اللوب الخاص به لأي شخص
                elif user.id in self.active_reaction_loops:
                    info = self.active_reaction_loops[user.id]
                    task = info.get("task")
                    if task and not task.done():
                        task.cancel()
                        await self.safe_whisper(user.id, f"🛑 تم إيقاف لوب الرياكشن على @{info.get('target')}")
                return
            
            parts = message.strip().split()
            if not parts:
                return
            

            
            # 🛡️ تحليل أولي للرسالة: هل هي دردشة عادية أم محاولة أمر؟
            # إذا بدأت الرسالة بكلمة شائعة أطول من 3 كلمات بدون @، نعتبرها دردشة
            common_words = ["لا", "ما", "من", "على", "في", "يا", "ان", "هل", "كل", "اي", "كنت", "كان", "باي", "هاي", "هلا", "بشر"]
            is_likely_sentence = len(parts) > 2 and parts[0].lower() in common_words and "@" not in message
            
            # 💫 نظام التفاعل المزدوج (Interaction System) - أولوية قصوى
            if len(parts) >= 2 and not is_likely_sentence:
                cmd = parts[0].lower()
                target_name = parts[1]
                is_loop = False
                
                # التحقق من وجود كلمة لوب
                if len(parts) >= 3 and parts[2].lower() in ["لوب", "loop", "تكرار"]:
                    is_loop = True

                # البحث في التفاعلات
                interaction_found = None
                for key, data in self.interactions.items():
                    if cmd in data["en"] or cmd in data["ar"]:
                        interaction_found = data
                        break
                
                if interaction_found:
                    await self.perform_interaction(user, target_name, interaction_found, is_loop)
                    return

            # 💫 نظام الرقص الثنائي القديم (رقصات عادية) - أولوية ثانية
            if len(parts) >= 2 and parts[1].lower() not in ["loop", "لوب", "تكرار"] and not is_likely_sentence:
                # 💃 أولاً: فحص إذا كان رقم رقصة
                try:
                    dance_num = int(parts[0])
                    if 1 <= dance_num < len(self.emote_list):
                        # رقص ثنائي بالرقم (مع لوب)
                        await self.dance_with_user(user, parts[1], dance_num)
                        return
                except ValueError:
                    pass
                
                # ثانياً: فحص إذا كان اسم رقصة (إنجليزي أو عربي)
                first_word = parts[0].lower()
                
                for emote_key, emote in self.emotes.items():
                    # فحص الاسم الإنجليزي (مفتاح القاموس)
                    if emote_key.lower() == first_word:
                        await self.dance_with_user(user, parts[1], emote_key)
                        return
                    # فحص الأسماء العربية
                    for ar_name in emote.get("ar", []):
                        if ar_name.lower() == first_word:
                            await self.dance_with_user(user, parts[1], emote_key)
                            return
            
            # نظام الرياكشنات - أولوية عالية
            if not is_likely_sentence:
                # ── فحص الصيغة المكوّنة من 3 كلمات مع "لوب" في النهاية ──
                if len(parts) == 3 and parts[2].lower() in ["لوب", "loop", "تكرار"]:
                    reaction_found = None
                    target_username = None
                    
                    # الصيغة: رياكشن يوزر لوب
                    possible_reaction = parts[0].lower()
                    possible_target   = parts[1]
                    for reaction_key, reaction_data in self.reactions.items():
                        if possible_reaction in reaction_data["ar"]:
                            reaction_found = reaction_key
                            target_username = possible_target
                            break
                    
                    # الصيغة المعكوسة: يوزر رياكشن لوب
                    if not reaction_found:
                        possible_reaction = parts[1].lower()
                        possible_target   = parts[0]
                        for reaction_key, reaction_data in self.reactions.items():
                            if possible_reaction in reaction_data["ar"]:
                                reaction_found = reaction_key
                                target_username = possible_target
                                break
                    
                    if reaction_found and target_username:
                        # اللوب للمالكين فقط
                        if not self.is_owner(user):
                            await self.safe_whisper(user.id, "❌ لوب الرياكشنات للمالكين فقط! 👑")
                            return
                        
                        target_user = await self.get_user_by_name(target_username.replace("@", ""))
                        if not target_user:
                            await self.safe_whisper(user.id, f"❌ لم يتم العثور على: {target_username}")
                            return
                        if target_user.id == self.highrise.my_id:
                            await self.safe_whisper(user.id, "❌ لا يمكن إرسال رياكشنات للبوت!")
                            return
                        
                        # إيقاف أي لوب سابق لهذا المالك
                        if user.id in self.active_reaction_loops:
                            old_task = self.active_reaction_loops[user.id].get("task")
                            if old_task and not old_task.done():
                                old_task.cancel()
                                await asyncio.sleep(0.2)
                        
                        # تشغيل اللوب اللانهائي
                        task = asyncio.create_task(
                            self.loop_reactions(target_user.id, target_user.username, reaction_found, user.id)
                        )
                        self.active_reaction_loops[user.id] = {
                            "task": task,
                            "target": target_user.username,
                            "type": reaction_found
                        }
                        await self.highrise.chat(f"💝 بدأ لوب {reaction_found} على @{target_user.username} بلا توقف! (اكتب وقف_رياكشن للإيقاف)")
                        return
                
                # ── فحص الصيغة العادية: كلمتان (رياكشن + يوزر) ──
                if len(parts) == 2:
                    # التحقق إذا كان الشخص يحاول استخدام h all أو r all
                    # نترك هذه الأوامر لـ handle_command
                    if parts[1].lower() == "all" or parts[0].lower() == "all":
                        pass # سيتم معالجتها في handle_command
                    else:
                        possible_reaction1 = parts[0].lower()
                        target_username1 = parts[1]
                        target_username2 = parts[0]
                        possible_reaction2 = parts[1].lower()
                        
                        reaction_found = None
                        target_username = None
                        
                        for reaction_key, reaction_data in self.reactions.items():
                            if possible_reaction1 in reaction_data["ar"]:
                                reaction_found = reaction_key
                                target_username = target_username1
                                break
                        
                        if not reaction_found:
                            for reaction_key, reaction_data in self.reactions.items():
                                if possible_reaction2 in reaction_data["ar"]:
                                    reaction_found = reaction_key
                                    target_username = target_username2
                                    break
                        
                        if reaction_found and target_username:
                            await self.send_reactions(user, target_username, reaction_found)
                            return
            
            # 🕊️ قائمة الرقصات المسموحة على السجادة (الراحة والتمدد فقط)
            allowed_rest_ids = [
                "sit-open", "idle_layingdown2", "idle-floorsleeping2", 
                "sit-relaxed", "idle-loop-sitfloor", "idle-floorsleeping", 
                "idle-sleep", "idle_layingdown"
            ]
            
            # نظام الرقصات
            if len(parts) == 1:
                try:
                    dance_num = int(parts[0])
                    if 1 <= dance_num < len(self.emote_list):
                        emote_data = self.emote_list[dance_num]
                        # منع الرقصات غير المريحة على السجادة
                        if user.id in self.carpet_users and emote_data["id"] not in allowed_rest_ids:
                            await self.safe_whisper(user.id, "⚠️ نعتذر، على السجادة السحرية مسموح فقط برقصات الراحة والتمدد! 🧘‍♂️")
                            return
                        await self.user_dance(user, dance_num, enable_loop=True) 
                        return
                except (ValueError, IndexError):
                    pass
            
            # التحقق إذا الرسالة اسم رقصة
            if len(parts) == 1:
                loop_it = user.id in self.carpet_users
                for emote_key, emote in self.emotes.items():
                    if emote_key.lower() == msg_lower or any(ar.lower() == msg_lower for ar in emote.get("ar", [])):
                        # منع الرقصات غير المريحة على السجادة
                        if user.id in self.carpet_users and emote["id"] not in allowed_rest_ids:
                             await self.safe_whisper(user.id, "⚠️ نعتذر، على السجادة السحرية مسموح فقط برقصات الراحة والتمدد! 🧘‍♂️")
                             return
                        await self.user_dance(user, emote_key, enable_loop=loop_it)
                        return

            # التحقق إذا الرسالة اسم رقصة + "لوب"
            elif len(parts) == 2 and parts[1].lower() in ["لوب", "loop"]:
                loop_word = parts[0].lower()
                for emote_key, emote in self.emotes.items():
                    if emote_key.lower() == loop_word or any(ar.lower() == loop_word for ar in emote.get("ar", [])):
                        # منع الرقصات غير المريحة على السجادة
                        if user.id in self.carpet_users and emote["id"] not in allowed_rest_ids:
                            await self.safe_whisper(user.id, "⚠️ على السجادة مسموح فقط برقصات الراحة والتمدد!")
                            return
                        await self.user_dance(user, emote_key, enable_loop=True)
                        return
            
            # فحص الكلمات المحظورة
            if self.auto_mod:
                for word in self.banned_words:
                    if word.lower() in msg_lower:
                        await self.warn_user(user, "استخدام كلمات محظورة")
                        return
            
            # 🛡️ نظام التحليل الذكي المطور (الإنذارات والسحب)
            is_distinguished = user.username.lower() in [d.lower() for d in self.distinguished_users]
            if not is_admin_user and not is_distinguished and self.auto_mod:
                try:
                    violation = await self.analyze_violation(message, user.username)
                    if (violation == "BEGGING" and self.begging_protection) or \
                       (violation == "INSULT" and self.insult_protection):
                        # زيادة العداد
                        self.violation_counts[user.id] = self.violation_counts.get(user.id, 0) + 1
                        count = self.violation_counts[user.id]
                        
                        v_type = "طلب جولد" if violation == "BEGGING" else "إساءة"
                        
                        # سحب اللاعب لمواجهة البوت
                        try:
                            pull_pos = Position(self.bot_position.x + 0.4, self.bot_position.y, self.bot_position.z + 0.4, "FrontRight")
                            await self.highrise.teleport(user.id, pull_pos)
                        except: pass

                        if count == 1:
                            # إنذار أول
                            await self.safe_chat(f"⚠️ @{user.username} ممنوع {v_type}! هذا إنذار أول، التزم بالقوانين.")
                            return
                        else:
                            # عقوبة كاملة (كتم + تجميد)
                            await self.safe_chat(f"🚫 @{user.username} تكرار {v_type}! تم كتمك وتثبيتك دقيقتين 🔇")
                            
                            # 1. التجميد المحلي (آمن ومستقر)
                            self.frozen_users[user.id] = pull_pos
                            self.muted_users[user.id] = True
                            
                            # 2. محاولة الكتم الرسمي (لكي تختفي الرسائل عن الجميع)
                            try:
                                await self.highrise.moderate_room(user.id, "mute", 120)
                            except Exception as e:
                                print(f"Official mute failed (maybe not moderator): {e}")

                            async def release_after(uid=user.id):
                                await asyncio.sleep(120)
                                self.frozen_users.pop(uid, None)
                                self.muted_users.pop(uid, None)
                            asyncio.create_task(release_after())
                            return
                except Exception as e:
                    print(f"Moderation logic error: {e}")

            # الحماية من السبام
            if self.spam_protection:
                if await self.check_spam(user):
                    # تخطي المشرفين والملاك من تحذير السبام
                    if not is_admin_user:
                        await self.warn_user(user, "السبام")
                        return
            
            # معالجة الأوامر
            await self.handle_command(user, message)
            
        except Exception as e:
            print(f"Error in on_chat: {e}")
            import traceback
            traceback.print_exc()

    async def user_dance(self, user: User, dance_num, enable_loop: bool = False, silent: bool = False):
        """جعل المستخدم يرقص - مع نظام منع التداخل والتحقق من الرقصة"""
        try:
            # 1. منع ترقيص البوت من الآخرين
            if user.id == self.highrise.my_id:
                pass 

            # 2. نظام تتبع الطلبات لمنع التداخل عند السرعة
            import time
            request_id = time.time()
            self.active_dance_requests[user.id] = request_id

            # 3. إيقاف أي مهمة رقص سابقة
            if user.id in self.dancing_users:
                self.dancing_users[user.id].cancel()
                try:
                    del self.dancing_users[user.id]
                except: pass

            # 4. تحديد الرقصة (رقم أو اسم)
            emote = None
            if isinstance(dance_num, int):
                if 1 <= dance_num < len(self.emote_list):
                    emote = self.emote_list[dance_num]
            elif isinstance(dance_num, str):
                emote = self.emotes.get(dance_num)
            
            if not emote:
                 await self.highrise.send_whisper(user.id, f"❌ لم أجد هذه الرقصة: {dance_num}")
                 return

            # 5. تجهيز نص الرسالة
            dance_name_str = ""
            dance_number_str = ""
            
            # البحث عن الاسم العربي للرقصة
            for k, v in self.emotes.items():
                if v["id"] == emote["id"]:
                    dance_name_str = k
                    break
            
            if not dance_name_str:
                dance_name_str = dance_num if isinstance(dance_num, str) else "رقصة"

            # إيجاد رقم الرقصة من القائمة
            try:
                idx = self.emote_list.index(emote)
                dance_number_str = str(idx)
            except:
                dance_number_str = str(dance_num) if isinstance(dance_num, int) else "?"
            
            if enable_loop:
                msg = f"💃 رقصة: {dance_name_str} (رقم {dance_number_str}) - مستمر"
            else:
                msg = f"💃 رقصة رقم: {dance_number_str}"

            # 6. إرسال الرقصة (مع دعم البديل المجاني)
            await self.safe_send_emote(emote["id"], user.id)
            
            # 7. التأكد أن الطلب لا يزال صالحاً (لم يتم استبداله بطلب أسرع)
            if self.active_dance_requests.get(user.id) != request_id:
                return

            if not silent:
                await self.highrise.send_whisper(user.id, msg)

            # 8. تشغيل اللوب إذا طلب المستخدم
            if enable_loop:
                task = asyncio.create_task(self.loop_dance(user.id, emote))
                self.dancing_users[user.id] = task
                self.user_active_emote[user.id] = dance_num if isinstance(dance_num, str) else dance_name_str
            
        except Exception as e:
            print(f"Error in user_dance: {e}")
            import traceback
            traceback.print_exc()
            try:
                await self.highrise.send_whisper(user.id, "❌ حدث خطأ بسيط في تشغيل الرقصة")
            except: pass
    
    async def dance_with_user(self, requester: User, target_username: str, dance_num):
        """
        الرقص الثنائي - أنت + يوزر ترقصوا نفس الرقصة مع لوب
        الصيغة: <رقم> <يوزر> أو <اسم_رقصة> <يوزر>
        """
        try:
            # ✅ منع ترقيص البوت
            target_user = await self.get_user_by_name(target_username)
            
            if not target_user:
                await self.highrise.send_whisper(requester.id, f"❌ لم يتم العثور على: {target_username}")
                return
            
            # ✅ منع ترقيص البوت
            bot_user_id = self.highrise.my_id
            if target_user.id == bot_user_id:
                await self.highrise.send_whisper(requester.id, "❌ ممنوع ترقيص البوت!")
                return
            
            # التأكد من وجود الرقصة
            emote = None
            
            # ✅ دعم الأرقام (عبر القائمة) والأسماء (عبر القاموس)
            if isinstance(dance_num, int):
                if 1 <= dance_num < len(self.emote_list):
                    emote = self.emote_list[dance_num]
            elif isinstance(dance_num, str):
                emote = self.emotes.get(dance_num)
                
            if not emote:
                await self.highrise.send_whisper(requester.id, f"❌ رقصة غير صحيحة!")
                return
            
            # ✨ حماية الملاك والمشرفين والمتميزين من الرقصات غير المرغوب فيها
            can_do, msg = await self.can_moderate(requester, target_user)
            if not can_do:
                await self.highrise.send_whisper(requester.id, f"❌ {msg}")
                return

            is_distinguished = target_user.username.lower() in [u.lower() for u in self.distinguished_users]
            
            if is_distinguished:
                # التحقق إذا كان الشخص الذي يطلب الرقص ليس مشرفاً أو الطرف المتميز نفسه
                if not await self.is_admin(requester) and requester.id != target_user.id:
                    await self.highrise.send_whisper(requester.id, f"🛡️ @{target_user.username} شخص مميز، لا يمكنك إجباره على الرقص!")
                    return
            
            # إيقاف أي رقص سابق للطرفين
            if requester.id in self.dancing_users:
                self.dancing_users[requester.id].cancel()
                del self.dancing_users[requester.id]
            
            if target_user.id in self.dancing_users:
                self.dancing_users[target_user.id].cancel()
                del self.dancing_users[target_user.id]
            
            # إرسال نفس الرقصة للاثنين
            await asyncio.gather(
                self.highrise.send_emote(emote["id"], requester.id),
                self.highrise.send_emote(emote["id"], target_user.id)
            )
            
            # إنشاء لوب للاثنين
            task1 = asyncio.create_task(self.loop_dance(requester.id, emote))
            task2 = asyncio.create_task(self.loop_dance(target_user.id, emote))
            
            self.dancing_users[requester.id] = task1
            self.dancing_users[target_user.id] = task2
            
        except Exception as e:
            print(f"Error in dance_with_user: {e}")


    async def group_dance(self, admin: User, target_username: str, dance_num):
        """رقص جماعي - المشرف + اللاعب يرقصوا نفس الرقصة"""
        try:
            target_user = await self.get_user_by_name(target_username)
            if not target_user:
                await self.highrise.chat(f"❌ لم يتم العثور على: {target_username}")
                return
            
            emote = None
            
            # ✅ دعم الأرقام (عبر القائمة) والأسماء (عبر القاموس)
            if isinstance(dance_num, int):
                if 1 <= dance_num < len(self.emote_list):
                    emote = self.emote_list[dance_num]
            elif isinstance(dance_num, str):
                emote = self.emotes.get(dance_num)
            
            if not emote:
                await self.highrise.chat(f"❌ رقصة غير صحيحة!")
                return
            
            # ✅ نظام الحماية في الرقص الجماعي
            can_do, msg = await self.can_moderate(admin, target_user)
            if not can_do:
                await self.highrise.chat(f"❌ {msg}")
                return

            if admin.id in self.dancing_users:
                self.dancing_users[admin.id].cancel()
                del self.dancing_users[admin.id]
            
            if target_user.id in self.dancing_users:
                self.dancing_users[target_user.id].cancel()
                del self.dancing_users[target_user.id]
            
            await asyncio.gather(
                self.highrise.send_emote(emote["id"], admin.id),
                self.highrise.send_emote(emote["id"], target_user.id)
            )
            
            await self.highrise.chat(f"💃🕺 {admin.username} و {target_user.username} يرقصون رقصة {dance_num} معاً!")
            
            task1 = asyncio.create_task(self.loop_dance(admin.id, emote))
            task2 = asyncio.create_task(self.loop_dance(target_user.id, emote))
            self.dancing_users[admin.id] = task1
            self.dancing_users[target_user.id] = task2
            
        except Exception as e:
            print(f"Error in group_dance: {e}")
            await self.highrise.chat(f"❌ خطأ في الرقص الجماعي")
    
    async def stop_dance(self, user: User):
        """إيقاف رقص المستخدم وأي تفاعلات ثنائية"""
        try:
            # إلغاء الطلبات المعلقة
            if user.id in self.active_dance_requests:
                del self.active_dance_requests[user.id]
                
            if user.id in self.dancing_users:
                task = self.dancing_users[user.id]
                # إلغاء المهمة
                if not task.done():
                    task.cancel()
                
                # إزالة أي مراجع لهذه المهمة لشركاء التفاعل
                partners_to_clear = [uid for uid, t in self.dancing_users.items() if t == task]
                for uid in partners_to_clear:
                    if uid in self.dancing_users:
                        del self.dancing_users[uid]
                    if uid in self.user_active_emote:
                        del self.user_active_emote[uid]
                
                print(f"Stopped dance task for {user.username} and interaction partners: {partners_to_clear}")
            
            # محاولة إظهار رمز إيقاف
            try:
                await self.highrise.send_emote("emote-no", user.id)
            except: pass
            
            await self.safe_whisper(user.id, "🛑 توقفت عن الرقص / التفاعل")
            
        except Exception as e:
            print(f"Error stopping dance: {e}")
    
    async def loop_dance(self, user_id: str, emote: dict):
        """تكرار الرقصة للأبد"""
        try:
            while True:
                if not self.connection_active:
                    break
                delay = max(emote["dur"], 3.0)
                await asyncio.sleep(delay)
                await self.safe_send_emote(emote["id"], user_id)
        except asyncio.CancelledError:
            print(f"Stopped dance loop for {user_id}")
        except Exception as e:
            print(f"Error in loop_dance: {e}")
    
    async def bot_auto_dance(self):
        """البوت يرقص تلقائياً - يتبدل بين جميع الرقصات المطلوبة"""
        dance_keys = ["floss", "swag", "ViralGroove", "PopularVibe", "Twerk", "Griddy", "TrueHeart"]
        current_idx = 0
        
        while self.bot_dancing and self.connection_active:
            try:
                if not self.connection_active:
                    break
                    
                key = dance_keys[current_idx]
                emote = self.emotes.get(key)
                if not emote:
                    # Fallback if key not found (shouldn't happen)
                    current_idx = (current_idx + 1) % len(dance_keys)
                    continue
                
                await self.highrise.send_emote(emote["id"])
                
                # وقت الرقصة + قليل من التأخير
                delay = max(emote["dur"] + 0.5, 5.0)
                await asyncio.sleep(delay)
                
                # الانتقال للرقصة التالية
                current_idx = (current_idx + 1) % len(dance_keys)
                
            except asyncio.CancelledError:
                print("Bot auto-dance stopped")
                break
            except Exception as e:
                error_msg = str(e)
                if "transport" in error_msg.lower() or "closing" in error_msg.lower():
                    print("Connection lost detected. Stopping dance task.")
                    self.connection_active = False
                    break
                if "User not in room" not in error_msg:
                    print(f"Error in bot auto-dance: {e}")
                await asyncio.sleep(5)
    
    async def safe_send_emote(self, emote_id, user_id, fallback_id="emote-tired"):
        """محاولة إرسال رقصة، وإذا فشلت (لعدم الملكية) نرسل رقصة بديلة مجانية"""
        try:
            await self.highrise.send_emote(emote_id, user_id)
        except Exception as e:
            # إذا فشل بسبب عدم الملكية، نرسل البديل
            if "owned" in str(e) or "free" in str(e):
                try:
                    await self.highrise.send_emote(fallback_id, user_id)
                except:
                    pass
            else:
                print(f"Error sending emote {emote_id}: {e}")

    async def perform_interaction(self, user: User, target_username: str, interaction: dict, is_loop: bool = False):
        """تنفيذ تفاعل بين مستخدمين (فاعل ومفعول به)"""
        try:
            target_user = await self.get_user_by_name(target_username)
            if not target_user:
                await self.highrise.send_whisper(user.id, f"❌ لم يتم العثور على: {target_username}")
                return
            
            # منع التفاعل مع البوت (بشكل عام)
            if target_user.id == self.highrise.my_id:
                await self.highrise.send_whisper(user.id, "❌ لا يمكنك فعل ذلك مع البوت!")
                return
            
            # ✨ حماية الملاك والمشرفين والمتميزين من التفاعلات
            can_do, msg = await self.can_moderate(user, target_user)
            if not can_do:
                await self.highrise.send_whisper(user.id, f"❌ {msg}")
                return

            is_distinguished = target_user.username.lower() in [u.lower() for u in self.distinguished_users]
            
            # تحديد التفاعلات "غير الجميلة"
            bad_interactions = ["slap", "punch", "kick", "stab", "shoot", "bite", "scare", "laugh"]
            
            if is_distinguished:
                # التحقق إذا كان التفاعل في القائمة السوداء
                interaction_key = next((k for k, v in self.interactions.items() if v == interaction), "unknown")
                if interaction_key in bad_interactions:
                    await self.highrise.send_whisper(user.id, f"🛡️ هذا الشخص مميز! لا يمكنك استخدام رقصات مخلة أو تفاعلات مزعجة معه.")
                    return
            
            # إيقاف أي رقص سابق للطرفين إذا كان لوب
            if is_loop:
                if user.id in self.dancing_users:
                    self.dancing_users[user.id].cancel()
                if target_user.id in self.dancing_users:
                    self.dancing_users[target_user.id].cancel()
                
                await self.highrise.chat(f"🔥 {user.username} بدأ سلسلة {interaction['ar'][0]} على {target_user.username} (اكتبوا 0 للإيقاف)")
                
                task = asyncio.create_task(self.loop_interaction(user.id, target_user.id, interaction))
                self.dancing_users[user.id] = task
                self.dancing_users[target_user.id] = task
                
            else:
                # محاولة تنفيذ التفاعل مرة واحدة مع استخدام البديل الآمن
                await asyncio.gather(
                    self.safe_send_emote(interaction["id"], user.id, "emoji-angry"),
                    self.safe_send_emote(interaction["target_id"], target_user.id, "emote-tired")
                )
                await self.highrise.chat(f"🔥 {user.username} قام بـ {interaction['ar'][0]} {target_user.username}!")
            
        except Exception as e:
            print(f"Error in perform_interaction: {e}")

    async def loop_interaction(self, user_id: str, target_id: str, interaction: dict):
        """لوب التفاعل"""
        try:
            while True:
                if not self.connection_active:
                    break
                    
                await asyncio.gather(
                    self.safe_send_emote(interaction["id"], user_id, "emoji-angry"),
                    self.safe_send_emote(interaction["target_id"], target_id, "emote-tired")
                )
                delay = max(interaction["dur"] + 0.5, 3.0)
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in loop_interaction: {e}")
        finally:
            # تنظيف السجل عند انتهاء المهمة لأي سبب
            for uid in [user_id, target_id]:
                if uid in self.dancing_users and self.dancing_users[uid] == asyncio.current_task():
                    del self.dancing_users[uid]
                    if uid in self.user_active_emote:
                         del self.user_active_emote[uid]

    async def loop_swing(self, user_id: str):
        """المرجحة: نقل المستخدم باستمرار لأماكن عشوائية"""
        try:
            await self.highrise.chat("🌪️ بدأت المرجحة... (اكتب 0 للإيقاف)")
            while True:
                if not self.connection_active or user_id not in self.user_ids_in_room:
                    break
                
                # إحداثيات عشوائية آمنة 
                rx = random.uniform(1.5, 18.5)
                rz = random.uniform(1.5, 18.5)
                
                # الحفاظ على الطابق الحالي للمستخدم
                current_y = 0.0
                try:
                    res = await self.highrise.get_room_users()
                    for u, pos in getattr(res, 'content', []):
                        if u.id == user_id:
                            current_y = pos.y
                            break
                except: pass
                
                try:
                    await self.highrise.teleport(user_id, Position(rx, current_y, rz, "FrontLeft"))
                except Exception as e:
                    if "Not in room" in str(e): break
                    print(f"Swing teleport failed: {e}")
                await asyncio.sleep(2.0) 
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in loop_swing: {e}")
        finally:
            if user_id in self.dancing_users and self.dancing_users[user_id] == asyncio.current_task():
                del self.dancing_users[user_id]
                if user_id in self.user_active_emote:
                    del self.user_active_emote[user_id]
            
            # 🏠 إعادة المستخدم لمنتصف الغرفة عند التوقف
            if user_id in self.user_ids_in_room:
                try:
                    # إعادة لمنتصف الغرفة الأرضي (أو إحداثيات أرضية افتراضية)
                    await self.highrise.teleport(user_id, Position(10.0, 0.0, 10.0, "FrontLeft"))
                    await self.highrise.send_whisper(user_id, "🏠 تمت إعادتك لمنتصف الغرفة.")
                except: pass

    async def send_reactions(self, user: User, target_username: str, reaction_type: str):
        """Bot sends real reactions to target user"""
        print(f"send_reactions: {user.username} -> {target_username} ({reaction_type})")
        
        target_user = await self.get_user_by_name(target_username)
        if not target_user:
            await self.highrise.chat(f"❌ لم يتم العثور على المستخدم: {target_username}")
            return
        
        # ✅ منع إرسال رياكشنات للبوت والملاك والمشرفين
        bot_user_id = self.highrise.my_id
        is_owner = target_user.username.lower() in [o.lower() for o in self.owners]
        is_target_admin = await self.is_admin(target_user)
        is_requester_admin = await self.is_admin(user)
        
        if target_user.id == bot_user_id:
            await self.highrise.send_whisper(user.id, "❌ ممنوع إرسال رياكشنات للبوت!")
            return
        
        # ✅ نظام الرياكشن شغال للكل

        
        reaction_map = {
            "heart": {"reaction": "heart", "ar": ["قلب", "ق", "حب", "ح", "h"]},
            "thumbs": {"reaction": "thumbs", "ar": ["اعجاب", "ا", "لايك", "ثامز", "thumbs"]},
            "clap": {"reaction": "clap", "ar": ["تصفيق", "ت", "كلاب", "clap"]},
            "wave": {"reaction": "wave", "ar": ["تلويح", "تل", "باي", "wave"]},
            "wink": {"reaction": "wink", "ar": ["غمزة", "غ", "وينك", "wink"]},
        }
        
        reaction_name = None
        reaction_value = None
        
        for key, data in reaction_map.items():
            if reaction_type.lower() == key.lower() or reaction_type.lower() in data["ar"]:
                reaction_name = key
                reaction_value = data["reaction"]
                break
        
        if not reaction_value:
            reactions_list = "، ".join([f"{k}: {'/'.join(v['ar'])}" for k, v in reaction_map.items()])
            await self.highrise.chat(f"❌ رياكشن غير صحيح!\n💝 الرياكشنات المتاحة:\n{reactions_list}")
            return
        
        try:
            # ✅ إرسال الرياكشنات (تم تعديل العدد بناءً على طلب المستخدم)
            total_to_send = 25 
            await self.highrise.chat(f"💝 جاري إرسال {total_to_send} {reaction_name} لـ {target_user.username}...")
            
            # إرسال الرياكشنات في دفعات (Batches) لتكون أسرع وأكثر استقراراً
            for i in range(total_to_send):
                if not self.connection_active: break
                try:
                    await self.highrise.react(reaction_value, target_user.id)
                    # تقليل التأخير لكسر الأرقام، مع موازنة بسيطة للحفاظ على الاتصال
                    if i % 15 == 0:
                        await asyncio.sleep(0.05) 
                except: break
            
            await self.highrise.chat(f"✅ تم تنفيذ القصف القلبي لـ {target_user.username} بنجاح! 💝💥")
            
        except Exception as e:
            print(f"Error in reactions: {e}")

    async def loop_reactions(self, target_id: str, target_username: str, reaction_type: str, requester_id: str):
        """💝 لوب الرياكشنات - رياكشن واحد كل نصف ثانية (أكثر أماناً واستقراراً)"""
        try:
            while True:
                if not self.connection_active:
                    break
                
                # إرسال رياكشن واحد فقط
                await self.highrise.react(reaction_type, target_id)
                
                # انتظار ثانية ونصف (أمان عالي جداً)
                await asyncio.sleep(1.5)
        except asyncio.CancelledError:
            print(f"Reaction loop stopped for {target_username}")
        except Exception as e:
            print(f"Error in loop_reactions: {e}")
        finally:
                if self.active_reaction_loops[requester_id].get("task") == asyncio.current_task():
                    del self.active_reaction_loops[requester_id]

    async def handle_command(self, user: User, message: str, conversation_id: str = None):
        """معالجة أوامر البوت - مُصلحة بالكامل"""
        if message.startswith("!"):
            message = message[1:]
        
        parts = message.split()
        if not parts:
            return
            
        command = parts[0].lower()
        is_admin_user = await self.is_admin(user)
        
        # 🤖 معالجة الذكاء الاصطناعي في الـ DM (إذا لم يكن أمراً معروفاً)
        is_known_command = command in [
            "help", "مساعدة", "مساعده", "هيلب", "الاوامر", "الأوامر", "اوامر",
            "users", "مستخدمين", "يوزرز", "الاعبين", "اللاعبين", "ناس",
            "time", "وقت", "الوقت", "تايم", "ساعة", "الساعة", "كم", "الساعه",
            "bot", "بوت", "روبوت", "!loc", "!off", "off", "إطفاء", "اطفاء", "reboot", "restart",
            "نقل_سريع", "سريع", "fast_teleport", "smart_teleport", "اختصار", "shortcut", "set_heart", "قلب_سريع",
            "رقصات", "الرقصات", "emotes", "رقص", "game", "games", "ألعاب", "العاب", "لعبة", "لعبه",
            "رقصني", "dance_me", "ارقص_لي", "ارضي", "ground", "ارضيه", "الارضي", "تحت", "down", "نزلني", "نزول",
            "first", "up1", "الاول", "طابق_اول", "اول", "فوق", "طلعني", "طلوع",
            "second", "up2", "الثاني", "طابق_ثاني", "ثاني", "فوق2", "فوق_2", "vip", "شخصية_مهمة", "في_اي_بي", "في_اي_ب", "فيب", "vip1",
            "طوابق", "floors", "الطوابق", "اين", "وين", "h all", "ر", "قلوب", "قلوب_للكل",
            "addmod", "addadmin", "اضف_مشرف", "اضف_ادمن", "removemod", "removeadmin", "ازالة_مشرف", "ازل_مشرف", "ازالة_ادمن",
            "طرد", "kick", "إعلان", "اعلان", "أعلن", "announcement", "مسح", "clear", "تنظيف",
            "ban", "حظر", "احظر", "بان", "unban", "فك_حظر", "فك", "mute", "كتم", "اكتم", "ميوت",
            "unmute", "فك_كتم", "فك_الكتم", "warn", "تحذير", "حذر", "انذار", "tphere", "come", "جيب", "هات", "سحب", "br",
            "tip", "invites", "دعوة", "دعوه", "نسخ", "تقليد", "equip", "تبديل", "switch", "نقل", "move"
        ]

        if conversation_id and not is_known_command:
            # إذا كنا في DM والرسالة ليست أمراً، نرد بالذكاء الاصطناعي فوراً
            role = "لاعب عادي"
            if self.is_owner(user): role = "مالك"
            elif is_admin_user: role = "مشرف"
            
            ai_answer = await self.ask_ai(message, user_role=role, user_id=user.id)
            
            # 🛠️ تحليل الأوامر من الذكاء الاصطناعي في الـ DM
            clean_lines = []
            ai_lines = ai_answer.split("\n")
            for line in ai_lines:
                if line.strip().startswith("CMD:"):
                    cmd_to_run = line.strip().replace("CMD:", "", 1).strip()
                    if cmd_to_run:
                        asyncio.create_task(self.handle_command(user, cmd_to_run, conversation_id=conversation_id))
                else:
                    clean_lines.append(line)
            
            clean_answer = "\n".join(clean_lines).strip()
            if clean_answer:
                await self.safe_send(user.id, clean_answer, conversation_id=conversation_id)
            return

        if command in ["help", "مساعدة", "مساعده", "هيلب", "الاوامر", "الأوامر", "اوامر"]:

            await self.show_help(user, conversation_id=conversation_id)
            return
        
        elif command in ["users", "مستخدمين", "يوزرز", "الاعبين", "اللاعبين", "ناس"]:
            await self.list_users()
            return
        
        elif command in ["time", "وقت", "الوقت", "تايم", "ساعة", "الساعة", "كم", "الساعه"]:
            from datetime import datetime
            current_time = datetime.now().strftime("%H:%M:%S")
            await self.highrise.chat(f"⏰ الوقت الحالي: {current_time}")
            return
        
        elif command in ["bot", "بوت", "روبوت"]:
            await self.highrise.chat("🤖 أنا بوت إدارة الغرفة! استخدم: مساعدة")
            return

        elif command == "!loc":
            # أمر لمساعدة المستخدم في معرفة إحداثيات موقعه الحالي بدقة
            room_users = await self.highrise.get_room_users()
            for u, pos in getattr(room_users, 'content', []):
                if u.id == user.id:
                    coords_msg = f"📍 موقعك الحالي:\nX: {pos.x:.2f}\nY: {pos.y:.2f}\nZ: {pos.z:.2f}"
                    await self.safe_whisper(user.id, coords_msg)
                    break
            return

        elif command in ["!off", "off", "إطفاء", "اطفاء", "reboot", "restart"]:
            if self.is_owner(user):
                if command == "!off":
                    await self.highrise.chat("🛑 تم إيقاف البوت نهائياً بأمر المالك. وداعاً!")
                    self.should_stop = True
                    self.connection_active = False
                    return
                
                # أمر off أو reboot (إعادة تشغيل)
                await self.highrise.chat("😴 سأغيب لمدة 5 ثواني ثم أعود! (إعادة تشغيل)...")
                await asyncio.sleep(2)
                
                # تنفيذ إعادة التشغيل عبر المانجر/الرانر
                if self.runner and self.bot_name:
                    asyncio.create_task(self.runner.reboot(self.bot_name))
                else:
                    # في حال كان يشتغل لوحده بدون رانر (للاحتياط)
                    raise Exception("Manual Reboot")
            else:
                await self.safe_whisper(user.id, "❌ هذا الأمر للمالك فقط!")
            return
            
        elif command in ["نقل_سريع", "سريع", "fast_teleport", "smart_teleport"]:
            if self.is_owner(user):
                self.smart_teleport = not self.smart_teleport
                self.save_config()
                status = "✅ مشغل" if self.smart_teleport else "❌ مطفأ"
                await self.highrise.chat(f"🚀 ميزة النقل السريع بين الطوابق الآن: {status}")
            else:
                await self.safe_whisper(user.id, "👑 هذا الأمر خاص بالملاك فقط!")
            return

        elif command in ["اختصار", "shortcut", "set_heart", "قلب_سريع"]:
            if is_admin_user:
                if len(parts) < 3:
                    help_msg = (
                        "❌ الصيغة الجديدة للاختصارات:\n"
                        "1️⃣ للقلوب: اختصار <اسم/حرف> @الاسم\n"
                        "2️⃣ لأي أمر: اختصار <اسم/حرف> <الأمر> <@الاسم>\n"
                        "مثال: اختصار ديانا جلب @ديانا\n"
                        "مثال: اختصار ق @احمد (اختصار حرفي)"
                    )
                    await self.safe_whisper(user.id, help_msg)
                    return
                
                key = parts[1].lower()
                
                # إذا بدأ الجزء الثاني بـ @ فهو اختصار قلوب قديم
                if parts[2].startswith("@"):
                    target_name = parts[2].replace("@", "")
                    self.heart_shortcuts[key] = target_name
                    await self.highrise.chat(f"❤️ تم الحفظ! الكلمة ({key}) سترسل 50 قلب لـ @{target_name}")
                else:
                    # نظام الاختصارات الشامل
                    full_cmd = " ".join(parts[2:])
                    self.heart_shortcuts[key] = full_cmd
                    await self.highrise.chat(f"🚀 تم الحفظ! الكلمة ({key}) ستنفذ الآن: {full_cmd}")
                
                self.save_config()
            else:
                await self.safe_whisper(user.id, "🛡️ هذا الأمر للمشرفين والملاك فقط!")
            return
        
        elif command in ["رقصات", "الرقصات", "emotes", "رقص"]:
            emotes_help = """🕺 كيف ترقص؟
1. اكتب رقم رقصة (1-239)
2. اكتب: اسم_الرقصة (مثلاً: شافل)
3. اكتب: اسم_الرقصة لوب (للتكرار)
✨ رقصات مشهورة:
شافل، داب، تويرك، قيتار، انمي، بطل، زومبي
🛑 لإيقاف الرقص اكتب: 0"""
            await self.safe_whisper(user.id, emotes_help)
            return

        elif command in ["game", "games", "ألعاب", "العاب", "لعبة", "لعبه"]:
            games_msg = """🎮 الألعاب المتاحة قريباً:
1️⃣ لعبة الأسئلة (قريباً)
2️⃣ لعبة الجولد (قريباً)
✨ حالياً يمكنك استخدام: رقصني (ليختار البوت لك رقصة عشوائية)"""
            await self.safe_whisper(user.id, games_msg)
            return

        elif command in ["رقصني", "dance_me", "ارقص_لي"]:
             # اختيار رقصة عشوائية مع لوب
             try:
                 random_dance = random.randint(1, len(self.emote_list) - 1)
                 await self.user_dance(user, random_dance, enable_loop=True)
             except:
                 pass
             return
        

        
        # ═══════════════════════════════════════
        # 🏢 أوامر التنقل (للجميع - بدون اسم يوزر)
        # ═══════════════════════════════════════
        
        # 🏢 الأرضي
        elif command in ["ارضي", "ground", "ارضيه", "الارضي", "تحت", "down", "نزلني", "نزول"] and len(parts) == 1:
            try:
                await self.highrise.teleport(user.id, self.floors["ground"])
                self.user_floors[user.id] = "ground"
                await self.highrise.send_whisper(user.id, "🏢 انتقلت للطابق الأرضي")
            except Exception as e:
                await self.highrise.send_whisper(user.id, f"❌ خطأ: {e}")
            return
        
        # 🏬 الطابق الأول (فوق)
        elif (command in ["first", "up1", "الاول", "طابق_اول", "اول", "فوق", "طلعني", "طلوع"] and len(parts) == 1) or \
             (command in ["فوق", "up", "طلعني"] and len(parts) == 2 and parts[1] == "1"):
            try:
                await self.highrise.teleport(user.id, self.floors["floor1"])
                self.user_floors[user.id] = "floor1"
                await self.highrise.send_whisper(user.id, "🏬 انتقلت إلى (فوق)")
            except Exception as e:
                await self.highrise.send_whisper(user.id, f"❌ خطأ: {e}")
            return

        # 🏬 الطابق الثاني (فوق2)
        elif (command in ["second", "up2", "الثاني", "طابق_ثاني", "ثاني", "فوق2", "فوق_2"] and len(parts) == 1) or \
             (command in ["فوق", "up", "بثاني"] and len(parts) == 2 and parts[1] == "2"):
            try:
                await self.highrise.teleport(user.id, self.floors["floor2"])
                self.user_floors[user.id] = "floor2"
                await self.highrise.send_whisper(user.id, "🏬 انتقلت إلى (فوق2)")
            except Exception as e:
                await self.highrise.send_whisper(user.id, f"❌ خطأ: {e}")
            return
        
        # 💎 VIP
        elif command in ["vip", "شخصية_مهمة", "في_اي_بي", "في_اي_ب", "فيب", "vip1"] or \
             (command == "في" and len(parts) >= 3 and parts[1] == "اي" and parts[2] == "بي"):
            
            is_admin = await self.is_admin(user)
            is_owner = self.is_owner(user)
            
            # إذا كان الأمر يحتوي على اسم (مثلاً: vip @احمد)
            if len(parts) >= 2 or (command == "في" and len(parts) >= 4):
                if not (is_admin or is_owner):
                    await self.highrise.send_whisper(user.id, "❌ هذا الأمر مخصص للمشرفين والملاك لسحب المستخدمين!")
                    return
                
                # استخراج اسم المستخدم (سواء كان في parts[1] أو بعد "في اي بي")
                target_name = parts[1] if command != "في" else parts[3]
                target_name = target_name.replace("@", "")
                
                try:
                    target_user = await self.get_user_by_name(target_name)
                    if not target_user:
                        await self.highrise.send_whisper(user.id, f"❌ لم يتم العثور على: {target_name}")
                        return
                    
                    # تحقق من الصلاحيات للسحب لـ VIP
                    can_do, msg = await self.can_moderate(user, target_user)
                    if not can_do:
                        await self.highrise.send_whisper(user.id, f"❌ {msg}")
                        return

                    await self.highrise.teleport(target_user.id, self.floors["vip"])
                    self.user_floors[target_user.id] = "vip"
                    await self.highrise.chat(f"💎 تم سحب @{target_user.username} إلى طابق VIP")
                except Exception as e:
                    await self.highrise.send_whisper(user.id, f"❌ خطأ: {e}")
                return

            # إذا كان الأمر لنفس الشخص (فقط: vip)
            is_vip_player = user.username.lower() in [v.lower() for v in self.vip_users]
            if not is_admin and not is_owner and not is_vip_player:
                await self.highrise.send_whisper(user.id, "❌ طابق VIP مخصص للمشرفين والـ VIP والملاك فقط!")
                return
            try:
                await self.highrise.teleport(user.id, self.floors["vip"])
                self.user_floors[user.id] = "vip"
                await self.highrise.send_whisper(user.id, "💎 انتقلت إلى طابق VIP")
            except Exception as e:
                await self.highrise.send_whisper(user.id, f"❌ خطأ: {e}")
            return
        
        elif command in ["طوابق", "floors", "الطوابق", "اين", "وين"]:
            floors_info = """
🏢 الطوابق المتاحة:

🏢 الأرضي: ارضي / ground
🏬 فوق: فوق / first
🏬 فوق2: فوق2 / second
💎 VIP: vip (للمشرفين والـ VIP)

✨ انقر على أي نقطة في طابق آخر
   وسينقلك بالضبط للمكان! 🎯
"""
            await self.highrise.send_whisper(user.id, floors_info)
            return
        
        if not is_admin_user:
            # رسالة للمستخدمين العاديين إذا حاولوا استخدام أمر مشرف
            admin_commands = ["طرد", "حظر", "كتم", "kick", "ban", "mute", "تحذير", "warn",
                            "جلب", "tphere", "come", "جيب", "هات", "سحب", "br", "روح", "tpto", "رح", "تجميد", "freeze", "جمد", "قل", "say",
                            "نقل_الكل", "r", "ر", "تحت", "down", "فوق", "up", "vip", "إعلان", "اعلان", "أعلن", "مسح", "تنظيف",
                            "addmod", "اضف_مشرف", "removemod", "ازالة_مشرف", "ازل_مشرف", "invite", "دعوة",
                            "switch", "تبديل", "بدل", "move", "نقل_موقع", "equip", "ارتدي", "لبس", "قلدني", "مثلي", "mimic", "ملابس",
                            "تعيين_سجادة", "setcarpet", "سجادة", "حذف_سجادة", "delcarpet",
                            "adddist", "تميز", "تمييز", "المرجحة", "مرجحة", "swing", "إيقاف_مرجحة", "unswing",
                            "لوب_رياكشن", "loop_reaction", "وقف_رياكشن", "stop_reaction"]
            
            if command in admin_commands:
                await self.highrise.send_whisper(user.id, "❌ مسموح فقط للمشرفين والـ VIP باستخدام هذا الأمر")
            return
        
        # ═══════════════════════════════════════
        # 👑 أوامر المشرفين (بعد التحقق)
        # ═══════════════════════════════════════
        
        # 💃 الرقص الجماعي: <رقم> <يوزر>
        if len(parts) == 2:
            try:
                dance_num = int(parts[0])
                if 1 <= dance_num < len(self.emote_list):
                    await self.group_dance(user, parts[1], dance_num)
                    return
            except ValueError:
                first_word = parts[0].lower()
                for emote_key, emote in self.emotes.items():
                    if emote_key.lower() == first_word:
                        await self.group_dance(user, parts[1], emote_key)
                        return
                    for ar_name in emote.get("ar", []):
                        if ar_name.lower() == first_word:
                            await self.group_dance(user, parts[1], emote_key)
                            return
        
        if (command == "h" and len(parts) > 1 and parts[1].lower() == "all") or command in ["r", "ر", "قلوب", "قلوب_للكل"]:
            try:
                room_users = await self.highrise.get_room_users()
                users_list = getattr(room_users, 'content', [])
                total_users = len(users_list)
                
                if total_users <= 1: # فقط البوت موجود
                    return

                await self.highrise.chat(f"💝 جاري توزيع القلوب المكثفة على الجميع ({total_users} لاعب)...")
                
                count = 0
                for player, _ in users_list:
                    if player.id != self.highrise.my_id:
                        try:
                            # إرسال قلب واحد لكل شخص (كما طلبت)
                            await self.highrise.react("heart", player.id)
                            count += 1
                            await asyncio.sleep(0.1) # تأخير بسيط جداً لضمان الاستقرار
                        except: pass
                
                await self.highrise.chat(f"✅ تم الانتهاء من توزيع القلوب لـ {count} لاعب! 💝💥")
            
            except Exception as e:
                print(f"Error in bulk hearts: {e}")
                await self.highrise.chat(f"❌ حدث خطأ")
            return
        
        # أوامر نقل اللاعبين
        elif command in ["تحت", "down"] and len(parts) >= 2:
            target_user = await self.get_user_by_name(parts[1])
            if target_user:
                if target_user.id == self.highrise.my_id:
                     await self.highrise.chat("❌ لا يمكنني نقل نفسي!")
                     return
                
                # حماية الملاك والمشرفين
                if self.is_owner(target_user) or await self.is_admin(target_user):
                    if not self.is_owner(user):
                        await self.highrise.send_whisper(user.id, "🛡️ لا يمكنك نقل الملاك أو المشرفين!")
                        return

                await self.highrise.teleport(target_user.id, self.floors["ground"])
                self.user_floors[target_user.id] = "ground"
                await self.highrise.chat(f"⬇️ تم نقل {parts[1]} تحت")
            else:
                await self.highrise.chat(f"❌ لم يتم العثور على: {parts[1]}")
            return
        
        elif command in ["فوق", "up"] and len(parts) >= 2:
            target_user = await self.get_user_by_name(parts[1])
            if target_user:
                if target_user.id == self.highrise.my_id:
                     await self.highrise.chat("❌ لا يمكنني نقل نفسي!")
                     return
                
                # حماية الملاك والمشرفين
                if self.is_owner(target_user) or await self.is_admin(target_user):
                    if not self.is_owner(user):
                        await self.highrise.send_whisper(user.id, "🛡️ لا يمكنك نقل الملاك أو المشرفين!")
                        return

                await self.highrise.teleport(target_user.id, self.floors["floor1"])
                self.user_floors[target_user.id] = "floor1"
                await self.highrise.chat(f"⬆️ تم نقل {parts[1]} فوق")
            else:
                await self.highrise.chat(f"❌ لم يتم العثور على: {parts[1]}")
            return
        
        elif command in ["vip", "في_اي_بي"] and len(parts) >= 2:
            target_user = await self.get_user_by_name(parts[1])
            if target_user:
                if target_user.id == self.highrise.my_id:
                     await self.highrise.chat("❌ لا يمكنني نقل نفسي!")
                     return
                
                # حماية الملاك والمشرفين
                if self.is_owner(target_user) or await self.is_admin(target_user):
                    if not self.is_owner(user):
                        await self.highrise.send_whisper(user.id, "🛡️ لا يمكنك نقل الملاك أو المشرفين!")
                        return

                await self.highrise.teleport(target_user.id, self.floors["vip"])
                self.user_floors[target_user.id] = "vip"
                await self.highrise.chat(f"💎 تم نقل {parts[1]} إلى طابق VIP")
            else:
                await self.highrise.chat(f"❌ لم يتم العثور على: {parts[1]}")
            return
        
        # ═══════════════════════════════════════
        # 💝 أوامر لوب الرياكشنات (للمالكين فقط)
        # ═══════════════════════════════════════
        elif command in ["لوب_رياكشن", "loop_reaction"]:
            # التحقق: المالك فقط
            if not self.is_owner(user):
                await self.safe_whisper(user.id, "❌ هذا الأمر للمالك فقط! 👑")
                return
            
            # الصيغة: لوب_رياكشن <نوع_رياكشن> <اسم_يوزر>
            # مثال: لوب_رياكشن قلب احمد
            if len(parts) < 3:
                await self.safe_whisper(user.id, "❌ الصيغة: لوب_رياكشن <رياكشن> <يوزر>\n💝 الأنواع: قلب / اعجاب / تصفيق / تلويح / غمزة")
                return
            
            reaction_input = parts[1].lower()
            target_name = parts[2].replace("@", "")
            
            # تحديد نوع الرياكشن
            reaction_map = {
                "heart":   ["قلب", "ق", "حب", "ح", "h", "heart"],
                "thumbs":  ["اعجاب", "ا", "لايك", "ثامز", "thumbs"],
                "clap":    ["تصفيق", "ت", "كلاب", "clap"],
                "wave":    ["تلويح", "تل", "باي", "wave"],
                "wink":    ["غمزة", "غ", "وينك", "wink"],
            }
            
            reaction_key = None
            for rk, aliases in reaction_map.items():
                if reaction_input in aliases:
                    reaction_key = rk
                    break
            
            if not reaction_key:
                await self.safe_whisper(user.id, "❌ رياكشن غير صحيح.\n💝 الأنواع: قلب / اعجاب / تصفيق / تلويح / غمزة")
                return
            
            # البحث عن المستخدم المستهدف
            target_user = await self.get_user_by_name(target_name)
            if not target_user:
                await self.safe_whisper(user.id, f"❌ لم يتم العثور على: {target_name}")
                return
            
            # منع إرسال رياكشنات للبوت نفسه
            if target_user.id == self.highrise.my_id:
                await self.safe_whisper(user.id, "❌ لا يمكن إرسال رياكشنات للبوت!")
                return
            
            # إيقاف أي لوب رياكشن سابق لهذا المالك
            if user.id in self.active_reaction_loops:
                old_task = self.active_reaction_loops[user.id].get("task")
                if old_task and not old_task.done():
                    old_task.cancel()
                    await asyncio.sleep(0.2)
            
            # إطلاق لوب الرياكشن اللانهائي
            task = asyncio.create_task(
                self.loop_reactions(target_user.id, target_user.username, reaction_key, user.id)
            )
            self.active_reaction_loops[user.id] = {"task": task, "target": target_user.username, "type": reaction_key}
            
            await self.highrise.chat(f"💝 بدأ لوب {reaction_key} على @{target_user.username} بلا توقف! (اكتب وقف_رياكشن للإيقاف)")
            return

        elif command in ["وقف_رياكشن", "stop_reaction"]:
            # المالك فقط
            if not self.is_owner(user):
                await self.safe_whisper(user.id, "❌ هذا الأمر للمالك فقط! 👑")
                return
            
            if user.id in self.active_reaction_loops:
                info = self.active_reaction_loops[user.id]
                task = info.get("task")
                if task and not task.done():
                    task.cancel()
                target_name = info.get('target', '؟')
                reaction_name = info.get('type', '؟')
                del self.active_reaction_loops[user.id]
                await self.highrise.chat(f"🛑 تم إيقاف لوب {reaction_name} عن @{target_name}")
            else:
                await self.safe_whisper(user.id, "❌ لا يوجد لوب رياكشن نشط حالياً!")
            return

        # أوامر المالك
        elif command in ["addmod", "addadmin", "اضف_مشرف", "اضف_ادمن"]:
            if user.username.lower() not in [o.lower() for o in self.owners]:
                await self.highrise.send_whisper(user.id, "❌ هذا الأمر للملاك فقط!")
                return
            if len(parts) >= 2:
                target_name = parts[1].replace("@", "")
                target_user = await self.get_user_by_name(target_name)
                
                if target_name.lower() not in [a.lower() for a in self.admins]:
                    self.admins.append(target_name)
                    self.save_config()
                    # إضافة لمشرفي الروم رسمياً
                    if target_user:
                        try:
                            await self.highrise.modify_room_privilege(target_user.id, RoomPermissions(moderator=True))
                            await self.highrise.chat(f"✅ تم إضافة @{target_name} كمشرف في البوت والروم 🛡️")
                        except Exception as e:
                            await self.highrise.chat(f"✅ تم إضافة @{target_name} كمشرف في البوت (فشل ترقية الروم: {e})")
                    else:
                        await self.highrise.chat(f"✅ تم إضافة @{target_name} كمشرف (سيتم ترقية الروم عند تواجده)")
                else:
                    await self.highrise.send_whisper(user.id, "❌ هذا المستخدم مشرف بالفعل")
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: اضف_مشرف أحمد")
            return
        
        elif command in ["removemod", "removeadmin", "ازالة_مشرف", "ازل_مشرف", "ازالة_ادمن"]:
            if user.username.lower() not in [o.lower() for o in self.owners]:
                await self.highrise.send_whisper(user.id, "❌ هذا الأمر للملاك فقط!")
                return
            if len(parts) >= 2:
                old_admin = parts[1].lower().replace("@", "")
                
                # 🛡️ حماية المطور NMR0
                if old_admin == "nmr0":
                    await self.highrise.chat("هاد الشخص مطوري وتاج راسي وما بقدر اسحب ملكيتو")
                    return

                original_admin = next((a for a in self.admins if a.lower() == old_admin), None)
                if original_admin:
                    self.admins.remove(original_admin)
                    self.save_config()
                    
                    # إزالة من مشرفي الروم رسمياً
                    target_user = await self.get_user_by_name(old_admin)
                    if target_user:
                        try:
                            await self.highrise.modify_room_privilege(target_user.id, RoomPermissions(moderator=False))
                            await self.highrise.chat(f"✅ تم إزالة إشراف @{original_admin} من البوت والروم")
                        except:
                            await self.highrise.chat(f"✅ تم إزالة إشراف @{original_admin} من البوت")
                    else:
                        await self.highrise.chat(f"✅ تم إزالة إشراف @{original_admin}")
                else:
                    await self.highrise.send_whisper(user.id, "❌ هذا المستخدم ليس مشرفاً")
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: ازالة_مشرف أحمد")
            return
        # باقي أوامر المشرفين
        elif command in ["طرد", "kick"]:
            if not is_admin_user: return
            if len(parts) >= 2:
                # محاولة طرد اللاعب مع التحقق الكامل
                await self.kick_user(parts[1], user)
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: طرد أحمد")
            return

        elif command in ["إعلان", "اعلان", "أعلن", "announcement"]:
            if not is_admin_user: return
            if len(parts) > 1:
                msg = " ".join(parts[1:])
                await self.highrise.chat("📢 إعــــلان هــــام 📢")
                await self.highrise.chat(f"✨ {msg} ✨")
            else:
                await self.safe_whisper(user.id, "❌ مثال: اعلان القهوة جاهزة يا شباب")
            return

        elif command in ["مسح", "clear", "تنظيف"]:
            if not is_admin_user: return
            # تنظيف الشات عبر إرسال رسائل فارغة كثيرة (أسلوب تقني)
            await self.highrise.chat("🧹 جاري تنظيف المجلس...")
            for _ in range(15):
                await self.highrise.chat("ㅤ") # حرف مخفي
            await self.highrise.chat("✅ تم تنظيف الشات بنجاح!")
            return
        
        elif command in ["ban", "حظر", "احظر", "بان"]:
            if len(parts) >= 2:
                duration = int(parts[2]) if len(parts) >= 3 else 3600
                await self.ban_user(parts[1], duration, user)
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: حظر أحمد")
            return
        
        elif command in ["unban", "فك_حظر", "فك"]:
            if len(parts) >= 2:
                await self.unban_user(parts[1])
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: فك أحمد")
            return
        
        elif command in ["mute", "كتم", "اكتم", "ميوت"]:
            if len(parts) >= 2:
                duration = int(parts[2]) if len(parts) >= 3 else 600
                await self.mute_user(parts[1], duration, user)
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: كتم أحمد")
            return
        
        elif command in ["unmute", "فك_كتم", "فك_الكتم"]:
            if len(parts) >= 2:
                await self.unmute_user(parts[1], user)
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: فك_كتم أحمد")
            return
        
        elif command in ["warn", "تحذير", "حذر", "انذار"]:
            if len(parts) >= 2:
                reason = " ".join(parts[2:]) if len(parts) > 2 else "مخالفة قوانين الغرفة"
                target = await self.get_user_by_name(parts[1])
                if target:
                    await self.warn_user(target, reason, user)
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: تحذير أحمد")
            return
        
        elif command in ["tphere", "come", "جيب", "هات", "سحب", "br"]:
            if len(parts) >= 2:
                target_user = await self.get_user_by_name(parts[1])
                if target_user:
                    if target_user.id == user.id: return
                    
                    # حماية الرتب
                    can_do, msg = await self.can_moderate(user, target_user)
                    if not can_do:
                        await self.highrise.send_whisper(user.id, f"❌ {msg}")
                        return

                    room_users = await self.highrise.get_room_users()
                    for u, pos in getattr(room_users, 'content', []):
                        if u.id == user.id:
                            await self.highrise.teleport(target_user.id, pos)
                            self.user_floors[target_user.id] = self._get_floor_name(pos.y) or "ground"
                            await self.highrise.chat(f"✅ تم جلب {parts[1]}")
                            break
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: جلب أحمد")
            return
        
        elif command in ["tpto", "روح", "رح", "روح_لـ"]:
            if len(parts) >= 2:
                target_user = await self.get_user_by_name(parts[1])
                if target_user:
                    room_users = await self.highrise.get_room_users()
                    for u, pos in getattr(room_users, 'content', []):
                        if u.id == target_user.id:
                            await self.highrise.teleport(user.id, pos)
                            await self.highrise.chat(f"✅ انتقل المشرف إلى {parts[1]}")
                            break
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: روح أحمد")
            return
        
        elif command in ["freeze", "تجميد", "جمد", "فريز", "تثبيت", "وقف", "ثبت"]:

            if len(parts) >= 2:
                await self.freeze_user(parts[1], user)
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: تجميد أحمد")
            return
        
        elif command in ["unfreeze", "فك_تجميد", "فك_التجميد"]:
            if len(parts) >= 2:
                await self.unfreeze_user(parts[1])
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: فك_تجميد أحمد")
            return
        
        elif command in ["إطلاق_سراح", "اطلاق_سراح", "release", "free", "حرر"]:
            if not is_admin_user: return
            if len(parts) >= 2:
                target_name = parts[1].replace("@", "")
                target_user = await self.get_user_by_name(target_name)
                if target_user:
                    # فك الكتم
                    if target_user.id in self.muted_users:
                        del self.muted_users[target_user.id]
                    # فك التثبيت
                    if target_user.id in self.frozen_users:
                        del self.frozen_users[target_user.id]
                    # محاولة فك الكتم الرسمي
                    try: await self.highrise.moderate_room(target_user.id, "mute", 1)
                    except: pass
                    
                    await self.highrise.chat(f"🕊️ تم إطلاق سراح @{target_user.username} وإلغاء كافة العقوبات!")
                else:
                    await self.highrise.chat(f"❌ لم يتم العثور على: {parts[1]}")
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: اطلاق_سراح أحمد")
            return

        # 🌪️ أمر المرجحة (للمشرفين والملاك)
        elif command in ["مرجح", "مرجحة", "swing", "swinging"]:
            if len(parts) >= 2:
                target_name = parts[1].replace("@", "")
                target_user = await self.get_user_by_name(target_name)
                if not target_user:
                    await self.safe_whisper(user.id, f"❌ لم أجد: {target_name}")
                    return
                
                # نظام الحماية الجديد
                can_do, msg = await self.can_moderate(user, target_user)
                if not can_do:
                    await self.safe_whisper(user.id, f"❌ {msg}")
                    return
                
                # إيقاف أي رقصة سابقة
                if target_user.id in self.dancing_users:
                    self.dancing_users[target_user.id].cancel()
                
                task = asyncio.create_task(self.loop_swing(target_user.id))
                self.dancing_users[target_user.id] = task
                await self.highrise.chat(f"🌪️ تم تفعيل المرجحة على @{target_user.username}")
            else:
                await self.safe_whisper(user.id, "❌ مثال: مرجحة @احمد")
            return

        # 🛑 أمر إيقاف المرجحة (للمشرفين والملاك)
        elif command in ["إيقاف_مرجحة", "ايقاف_مرجحة", "وقف_مرجحة", "unswing", "stop_swing"]:
            if len(parts) >= 2:
                target_name = parts[1].replace("@", "")
                target_user = await self.get_user_by_name(target_name)
                if target_user and target_user.id in self.dancing_users:
                    self.dancing_users[target_user.id].cancel()
                    await self.highrise.chat(f"🛑 تم إيقاف المرجحة عن @{target_user.username}")
                else:
                    await self.safe_whisper(user.id, "❌ هذا المستخدم ليس في حالة مرجحة حالياً")
            else:
                await self.safe_whisper(user.id, "❌ مثال: إيقاف_مرجحة @احمد")
            return

        # ═══════════════════════════════════════
        # 💰 توزيع الجولد
        # ═══════════════════════════════════════
        elif command in ["tip", "جولد", "اعطي"]:
            if not self.is_owner(user):
                await self.safe_whisper(user.id, "👑 هذا الأمر مخصص للملاك فقط (المالية)!")
                return
            await self.tip_user(user, parts)
            return

        # ═══════════════════════════════════════
        # 📨 الدعوات
        # ═══════════════════════════════════════
        elif command in ["invite", "دعوة", "دعوه"]:
            custom_msg = " ".join(parts[1:]) if len(parts) > 1 else ""
            await self.send_invites(user, custom_msg)
            return

        # ═══════════════════════════════════════
        # 👗 نسخ ملابس مستخدم
        # ═══════════════════════════════════════
        elif command in ["equip", "ارتدي", "لبس", "قلدني", "مثلي", "mimic", "ملابس"]:
            if len(parts) >= 2:
                # إذا تم توفير اسم مستخدم، نقوم بنسخ ملابسه
                await self.equip_bot_from_user(user, parts[1].replace("@", ""))
            else:
                # إذا لم يتم توفير اسم، يقلد ملابس الشخص الذي أرسل الأمر
                await self.equip_bot_from_user(user, user.username)
            return

        # ═══════════════════════════════════════
        # 🔄 تبديل المواقع
        # ═══════════════════════════════════════
        elif command in ["switch", "تبديل", "بدل"]:
            if len(parts) >= 2:
                await self.switch_positions(user, parts[1])
            else:
                await self.safe_whisper(user.id, "❌ مثال: switch اسم")
            return

        elif command in ["move", "نقل_موقع"]:
            if len(parts) >= 3:
                await self.move_users(user, parts[1], parts[2])
            else:
                await self.safe_whisper(user.id, "❌ مثال: move اسم1 اسم2")
            return

        # ═══════════════════════════════════════
        # ⭐ إدارة VIP
        # ═══════════════════════════════════════

        elif command in ["adddist", "تميز", "تمييز", "اضف_مميز"]:
            if not is_admin_user: return
            if len(parts) >= 2:
                new_dist = parts[1].replace("@", "")
                if new_dist.lower() not in [u.lower() for u in self.distinguished_users]:
                    self.distinguished_users.append(new_dist)
                    self.save_config()
                    await self.safe_chat(f"✨ تم إضافة @{new_dist} لقائمة التميز (محمي من التفاعلات المزعجة) 🛡️")
                else:
                    await self.safe_whisper(user.id, "❌ هذا المستخدم مميز بالفعل")
            else:
                await self.safe_whisper(user.id, "❌ مثال: تميز أحمد")
            return

        elif command in ["removedist", "الغاء_تميز", "حذف_مميز", "إلغاء_تميز"]:
            if not is_admin_user: return
            if len(parts) >= 2:
                old_dist = parts[1].replace("@", "").lower()
                # التحقق إذا كان المستهدف مشرف أو مميز والمالك فقط من يحق له
                target_user = await self.get_user_by_name(old_dist)
                if target_user:
                    can_do, msg = await self.can_moderate(user, target_user)
                    if not can_do:
                        await self.safe_whisper(user.id, f"❌ {msg}")
                        return

                original = next((u for u in self.distinguished_users if u.lower() == old_dist), None)
                if original:
                    self.distinguished_users.remove(original)
                    self.save_config()
                    await self.safe_chat(f"🛡️ تم إزالة @{original} من قائمة التميز")
                else:
                    await self.safe_whisper(user.id, "❌ هذا المستخدم ليس في قائمة التميز")
            else:
                await self.safe_whisper(user.id, "❌ مثال: الغاء_تميز أحمد")
            return

        elif command in ["distlist", "قائمة_التميز"]:
            if self.distinguished_users:
                dist_list = "\n".join([f"✨ @{u}" for u in self.distinguished_users])
                await self.safe_whisper(user.id, f"📝 قائمة المستخدمين المميزين:\n{dist_list}")
            else:
                await self.safe_whisper(user.id, "❌ لا يوجد مميزين")
            return
        elif command == "admin" and len(parts) >= 2 and parts[1].lower() in ["list", "قائمة"]:
            if self.admins:
                valid_admins = [a for a in self.admins if a]
                if valid_admins:
                    admins_str = ", ".join([f"🛡️ @{a}" for a in valid_admins])
                    await self.safe_whisper(user.id, f"🛡️ قائمة المشرفين:\n{admins_str}")
                else:
                    await self.highrise.chat("لا يوجد مشرفين حالياً")
            return

        elif command in ["نقل_الكل", "teleport_all"]:
            if len(parts) >= 2:
                floor_name = parts[1].lower()
                
                if floor_name in ["arضي", "ground", "0"]:
                    target_floor = self.floors["ground"]
                    floor_text = "الطابق الأرضي 🏢"
                elif floor_name in ["اول", "first", "1"]:
                    target_floor = self.floors["floor1"]
                    floor_text = "الطابق الأول 🏬"
                elif floor_name in ["ثاني", "second", "2"]:
                    target_floor = self.floors["floor2"]
                    floor_text = "الطابق الثاني 🏬"
                elif floor_name in ["vip", "في_اي_بي", "v"]:
                    target_floor = self.floors["vip"]
                    floor_text = "طابق VIP 💎"
                else:
                    await self.highrise.send_whisper(user.id, "❌ طابق غير صحيح")
                    return
                
                try:
                    room_users = await self.highrise.get_room_users()
                    count = 0
                    for u, _ in getattr(room_users, 'content', []):
                        if u.id != user.id:
                            # حماية الملاك والمشرفين والمميزين باستخدام نظام الصلاحيات الموحد
                            can_do, _ = await self.can_moderate(user, u)
                            is_distinguished = u.username.lower() in [d.lower() for d in self.distinguished_users]
                            
                            if not can_do or is_distinguished: 
                                continue
                            
                            await self.highrise.teleport(u.id, target_floor)
                            count += 1
                    
                    await self.highrise.chat(f"✅ تم نقل {count} مستخدم إلى {floor_text}")
                except Exception as e:
                    await self.highrise.chat(f"❌ خطأ: {e}")
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: نقل_الكل ارضي")
            return
        
        elif command in ["ترحيب", "welcome"]:
            if not self.is_owner(user):
                await self.safe_whisper(user.id, "👑 هذا الأمر مخصص للملاك فقط (إعدادات الترحيب)!")
                return
            if len(parts) >= 2:
                content = " ".join(parts[1:])
                if content.lower() in ["حذف", "مسح", "ازالة", "افتراضي", "0", "remove", "clear", "default"]:
                    self.welcome_message = ""
                    await self.highrise.chat("🔄 تم تفعيل الترحيب التلقائي باسم الروم 🌟")
                else:
                    self.welcome_message = content
                    welcome_type = "عامة 📢" if self.welcome_public else "همس 💬"
                    await self.highrise.chat(f"✅ تم تحديث رسالة الترحيب ({welcome_type})")
                self.save_config()
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: ترحيب أهلاً بك\nلفعل الترحيب التلقائي: ترحيب افتراضي")
            return
        
        elif command in ["نظام_الشحادة", "شحادة", "begging_protection"]:
            if is_admin_user:
                if len(parts) >= 2:
                    val = parts[1].lower()
                    if val in ["تشغيل", "on", "تفعيل"]: self.begging_protection = True
                    elif val in ["ايقاف", "off", "تعطيل"]: self.begging_protection = False
                else:
                    self.begging_protection = not self.begging_protection
                
                self.save_config()
                status = "🟢 مفعل" if self.begging_protection else "🔴 معطل"
                await self.highrise.chat(f"🛡️ نظام منع الشحادة: {status}")
            return

        elif command in ["نظام_السب", "سب", "insult_protection"]:
            if is_admin_user:
                if len(parts) >= 2:
                    val = parts[1].lower()
                    if val in ["تشغيل", "on", "تفعيل"]: self.insult_protection = True
                    elif val in ["ايقاف", "off", "تعطيل"]: self.insult_protection = False
                else:
                    self.insult_protection = not self.insult_protection
                
                self.save_config()
                status = "🟢 مفعل" if self.insult_protection else "🔴 معطل"
                await self.highrise.chat(f"🛡️ نظام منع السب: {status}")
            return
        
        elif command in ["welcometype", "نوع_الترحيب"]:
            if not self.is_owner(user):
                await self.safe_whisper(user.id, "👑 هذا الأمر مخصص للملاك فقط!")
                return
            self.welcome_public = not self.welcome_public
            self.save_config()
            welcome_type = "عامة 📢" if self.welcome_public else "همس 💬"
            await self.highrise.chat(f"✅ الترحيب الآن عبر الـ: {welcome_type}")
            return
        
        elif command in ["ترحيب_خاص", "customwelcome", "vip_welcome"]:
            if not self.is_owner(user):
                await self.safe_whisper(user.id, "👑 هذا الأمر مخصص للملاك فقط!")
                return
            if len(parts) >= 3:
                target_name = parts[1]
                if target_name.startswith("@"):
                    target_name = target_name[1:]
                
                custom_msg = " ".join(parts[2:])
                self.custom_welcomes[target_name.lower()] = custom_msg
                self.save_config()
                
                await self.highrise.chat(f"✅ تم تعيين ترحيب خاص لـ @{target_name}")
                await self.highrise.send_whisper(user.id, f"📝 الرسالة: {custom_msg}")
            elif len(parts) == 2 and parts[1].lower() in ["قائمة", "list"]:
                if self.custom_welcomes:
                    msg = "📋 الترحيبات الخاصة:\n"
                    for name, wmsg in self.custom_welcomes.items():
                        msg += f"• @{name}: {wmsg}\n"
                    await self.highrise.send_whisper(user.id, msg)
                else:
                    await self.highrise.send_whisper(user.id, "❌ لا توجد ترحيبات خاصة")
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: ترحيب_خاص @الاسم رسالة الترحيب")
            return
        
        elif command in ["حذف_ترحيب", "removewelcome"]:
            if not self.is_owner(user):
                await self.safe_whisper(user.id, "👑 هذا الأمر مخصص للملاك فقط!")
                return
            if len(parts) >= 2:
                target_name = parts[1].lower()
                if target_name.startswith("@"):
                    target_name = target_name[1:]
                if target_name in self.custom_welcomes:
                    del self.custom_welcomes[target_name]
                    self.save_config()
                    await self.highrise.chat(f"✅ تم حذف الترحيب الخاص لـ @{target_name}")
                else:
                    await self.highrise.send_whisper(user.id, f"❌ لا يوجد ترحيب خاص لـ @{target_name}")
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: حذف_ترحيب @الاسم")
            return

        elif command in ["wallet", "محفظة", "فلوس", "رصيد"]:
            # التحقق من رصيد البوت
            if not self.is_owner(user):
                await self.highrise.send_whisper(user.id, "❌ هذا الأمر للملاك فقط!")
                return
            try:
                res_wallet = await self.highrise.get_wallet()
                if hasattr(res_wallet, 'content'):
                    msg = "💰 رصيد البوت الحالي:"
                    found_currencies = False
                    for currency in res_wallet.content:
                        # تحويل أسماء العملات للعربية للتسهيل
                        c_type = currency.type
                        if c_type == "gold": c_type = "ذهب"
                        elif c_type == "bubbles": c_type = "فقاعات (Bubbles)"
                        
                        msg += f"\n- {c_type}: {currency.amount}"
                        found_currencies = True
                    
                    if not found_currencies:
                        msg += "\n(المحفظة فارغة 0)"
                        
                    await self.highrise.chat(msg)
                else:
                    await self.highrise.chat(f"❌ خطأ في جلب الرصيد: {res_wallet}")
            except Exception as e:
                await self.highrise.chat(f"❌ خطأ: {e}")
            return
        


        # استعراض المشرفين (للجميع)
        elif command in ["admins", "مشرفين", "المشرفين", "الادمنية"]:
            if self.admins:
                valid_admins = [a for a in self.admins if a]
                if valid_admins:
                    admins_str = ", ".join([f"@{a}" for a in valid_admins])
                    await self.highrise.chat(f"🛡️ مشرفو المجلس: {admins_str}")
                else:
                    await self.highrise.chat("لا يوجد مشرفين حالياً")
            else:
                await self.highrise.chat("لا يوجد مشرفين حالياً")
            return
        
        elif command in ["find", "بحث"]:
            if len(parts) >= 2:
                search_name = parts[1]
                user_found = await self.get_user_by_name(search_name)
                if user_found:
                    await self.highrise.chat(f"✅ وجدت المستخدم:\n📝 الاسم: @{user_found.username}\n🆔 المعرف: {user_found.id}")
                else:
                    await self.highrise.chat(f"❌ لم أجد مستخدم باسم: {search_name}")
            else:
                await self.highrise.send_whisper(user.id, "❌ مثال: بحث أحمد")
            return
        
        elif command in ["احداثيات", "موقعي", "pos", "position", "coords"]:
            try:
                room_users = await self.highrise.get_room_users()
                for u, pos in getattr(room_users, 'content', []):
                    if u.id == user.id:
                        position_info = f"""
📍 إحداثياتك:
━━━━━━━━━━━━━━━
X: {pos.x}
Y: {pos.y}
Z: {pos.z}
Facing: {pos.facing}
━━━━━━━━━━━━━━━
📋 للنسخ:
Position({pos.x}, {pos.y}, {pos.z}, "{pos.facing}")
"""
                        await self.highrise.send_whisper(user.id, position_info)
                        return
                await self.highrise.send_whisper(user.id, "❌ لم أتمكن من إيجاد موقعك")
            except Exception as e:
                await self.highrise.send_whisper(user.id, f"❌ خطأ: {e}")
            return
        
        # أوامر المالك فقط
        if self.is_owner(user):
            if command in ["هنا", "setbot", "set_bot"]:
                try:
                    room_users = await self.highrise.get_room_users()
                    for u, pos in getattr(room_users, 'content', []):
                        if u.id == user.id:
                            self.bot_position = pos
                            self.save_config()
                            # Teleport bot to the new location immediately
                            await self.highrise.teleport(self.highrise.my_id, self.bot_position)
                            await self.highrise.chat(f"📍 تم تحديد موقع البوت الجديد هنا @{user.username} وتم نقله!")
                            return
                    await self.highrise.send_whisper(user.id, "❌ لم أتمكن من العثور على موقعك لتحديد مكان البوت")
                except Exception as e:
                    print(f"Error in setbot command: {e}")
                    await self.highrise.send_whisper(user.id, f"❌ خطأ: {e}")
                return
            
            if command in ["تعيين_طابق", "setfloor", "set_floor"]:
                if len(parts) >= 2:
                    floor_name_query = " ".join(parts[1:]).lower().strip()
                    
                    # خريطة شاملة لجميع الاحتمالات (العربية والإنجليزية والأرقام)
                    # الهدف: تحويل أي كلمة للمفتاح البرمجي الصحيح (ground, floor1, floor2, vip)
                    standard_map = {
                        # الأرضي
                        "ground": "ground", "ارضي": "ground", "الارضي": "ground", "تحت": "ground", "نزول": "ground", "0": "ground", "ارض": "ground", "down": "ground", "نزلني": "ground",
                        # الأول
                        "floor1": "floor1", "اول": "floor1", "الاول": "floor1", "فوق": "floor1", "طابق_اول": "floor1", "فوق1": "floor1", "up": "floor1", "up1": "floor1", "1": "floor1", "طلعني": "floor1",
                        # الثاني
                        "floor2": "floor2", "ثاني": "floor2", "الثاني": "floor2", "فوق2": "floor2", "طابق_ثاني": "floor2", "up2": "floor2", "2": "floor2", "فوق_2": "floor2",
                        # VIP
                        "vip": "vip", "فيب": "vip", "v": "vip", "في اي بي": "vip", "شخصية مهمة": "vip", "vip1": "vip"
                    }
                    
                    target_key = None
                    # بحث مباشر عن الكلمة
                    if floor_name_query in standard_map:
                        target_key = standard_map[floor_name_query]
                    else:
                        # بحث عن كلمة مفتاحية داخل النص (مثل "اي بي" أو "2")
                        # نرتب الأكواد حسب الطول للأدق
                        sorted_aliases = sorted(standard_map.keys(), key=len, reverse=True)
                        for alias in sorted_aliases:
                            if alias in floor_name_query:
                                target_key = standard_map[alias]
                                break
                    
                    if not target_key:
                        await self.highrise.send_whisper(user.id, "❌ لم أفهم اسم الطابق. جرب: ارضي، فوق، فوق2، vip")
                        return

                    try:
                        room_users = await self.highrise.get_room_users()
                        user_pos = None
                        for u, pos in getattr(room_users, 'content', []):
                            if u.id == user.id:
                                user_pos = pos
                                break
                                
                        if user_pos:
                            self.floors[target_key] = user_pos
                            self.save_config()
                            # مسميات العرض العربية
                            ar_names = {"ground": "الأرضي", "floor1": "فوق (الأول)", "floor2": "فوق2 (الثاني)", "vip": "VIP"}
                            await self.highrise.chat(f"📍 تم حفظ موقعك لـ ({ar_names[target_key]}) بنجاح!")
                        else:
                            await self.highrise.send_whisper(user.id, "❌ لم أجد موقعك")
                    except Exception as e:
                        await self.highrise.send_whisper(user.id, f"❌ خطأ: {e}")
                else:
                    await self.highrise.send_whisper(user.id, "❌ مثال: تعيين_طابق فوق")
                return

            if command in ["تعيين_سجادة", "setcarpet", "سجادة"]:
                # الكشف التلقائي عن الاسم والنوع
                carpet_name = parts[1] if len(parts) >= 2 else f"سجادة_{len(self.carpets) + 1}"
                
                try:
                    room_users = await self.highrise.get_room_users()
                    for u, pos in getattr(room_users, 'content', []):
                        if u.id == user.id:
                            # تحديد النوع تلقائياً بناءً على الارتفاع
                            # أرضي (أقل من 5) -> ريست | فوق -> استرخاء
                            dance_type = "Rest" if pos.y < 5.0 else "Relaxed"
                            dance_name_ar = "ريست" if dance_type == "Rest" else "استرخاء"
                            
                            # حذف أي سجادة بنفس الاسم إذا وجدت
                            self.carpets = [c for c in self.carpets if c['name'] != carpet_name]
                            
                            # إضافة السجادة الجديدة
                            new_carpet = {
                                "name": carpet_name,
                                "x": pos.x,
                                "y": pos.y,
                                "z": pos.z,
                                "range": 1.25, # نطاق دقيق (متر وربع حول النقطة)
                                "emote": dance_type
                            }
                            self.carpets.append(new_carpet)
                            self.save_config()
                            await self.highrise.chat(f"🛋️ تم حفظ موقعك كسجادة فعاليات باسم ({carpet_name})")
                            await self.highrise.chat(f"✨ نوع الرقصة التلقائي: {dance_name_ar}")
                            return
                    await self.highrise.send_whisper(user.id, "❌ لم أتمكن من العثور على موقعك")
                except Exception as e:
                    await self.highrise.send_whisper(user.id, f"❌ خطأ: {e}")
                return

            if command in ["حذف_سجادة", "delcarpet"]:
                if len(parts) >= 2:
                    carpet_name = parts[1]
                    original_len = len(self.carpets)
                    self.carpets = [c for c in self.carpets if c['name'] != carpet_name]
                    if len(self.carpets) < original_len:
                        self.save_config()
                        await self.highrise.chat(f"🗑️ تم حذف السجادة ({carpet_name})")
                    else:
                        await self.safe_whisper(user.id, f"❌ لم أجد سجادة باسم: {carpet_name}")
                return

            if command in ["طوابق_افتراضية", "default_floors", "احداثيات_قياسية", "ريست_طوابق"]:
                self.floors = {
                    "ground": Position(10.0, 0.0, 10.0, "FrontLeft"),
                    "floor1": Position(15.0, 7.5, 15.0, "FrontLeft"),
                    "floor2": Position(10.0, 13.75, 10.0, "FrontRight"),
                    "vip":    Position(5.0, 15.75, 5.0, "FrontLeft"),
                }
                self.save_config()
                await self.highrise.chat("🔄 تم إعادة تعيين الطوابق للإحداثيات القياسية (أرضي 0 | أول 7.5 | ثاني 13.75 | VIP 15.75)")
                return
            
            # ⭐ إدارة VIP (حصرياً للملاك)
            if command in ["addvip", "اضف_vip", "اضافة_vip"]:
                if len(parts) >= 2:
                    new_vip = parts[1].replace("@", "")
                    if new_vip.lower() not in [v.lower() for v in self.vip_users]:
                        self.vip_users.append(new_vip)
                        self.save_config()
                        await self.safe_chat(f"⭐ تم إضافة @{new_vip} لقائمة VIP")
                    else:
                        await self.safe_whisper(user.id, "❌ هذا المستخدم في قائمة VIP بالفعل")
                else:
                    await self.safe_whisper(user.id, "❌ مثال: addvip اسم")
                return

            elif command in ["removevip", "ازالة_vip", "حذف_vip"]:
                if len(parts) >= 2:
                    old_vip = parts[1].replace("@", "").lower()
                    original = next((v for v in self.vip_users if v.lower() == old_vip), None)
                    if original:
                        self.vip_users.remove(original)
                        self.save_config()
                        await self.safe_chat(f"⭐ تم إزالة @{original} من قائمة VIP")
                    else:
                        await self.safe_whisper(user.id, "❌ هذا المستخدم ليس في قائمة VIP")
                else:
                    await self.safe_whisper(user.id, "❌ مثال: removevip اسم")
                return

            elif command == "vip" and len(parts) >= 2 and parts[1].lower() in ["list", "قائمة"]:
                if self.vip_users:
                    vip_list = "\n".join([f"⭐ @{v}" for v in self.vip_users])
                    await self.safe_whisper(user.id, f"⭐ قائمة VIP:\n{vip_list}")
                else:
                    await self.safe_whisper(user.id, "❌ قائمة VIP فارغة")
                return

            if command in ["addowner", "اضافة_مالك"]:
                if len(parts) >= 2:
                    new_owner = parts[1]
                    if new_owner.startswith("@"):
                        new_owner = new_owner[1:]
                    if new_owner.lower() not in [o.lower() for o in self.owners]:
                        self.owners.append(new_owner)
                        self.save_config()
                        await self.highrise.chat(f"👑 تم إضافة @{new_owner} كمالك جديد")
                    else:
                        await self.highrise.send_whisper(user.id, "❌ هذا المستخدم مالك بالفعل")
                else:
                    await self.highrise.send_whisper(user.id, "❌ مثال: اضافة_مالك أحمد")
                return
            
            elif command in ["removeowner", "ازالة_مالك"]:
                if len(parts) >= 2:
                    old_owner = parts[1].lower().replace("@", "")
                    
                    # 🛡️ حماية المطور NMR0 (تاج راسي)
                    if old_owner == "nmr0":
                        await self.highrise.chat("هاد الشخص مطوري وتاج راسي وما بقدر اسحب ملكيتو")
                        return

                    original_owner = next((o for o in self.owners if o.lower() == old_owner), None)
                    if original_owner:
                        # حماية المالك الأصلي من الإزالة
                        if self.room_owner_username and original_owner.lower() == self.room_owner_username.lower():
                            await self.highrise.send_whisper(user.id, "❌ خط أحمر! لا يمكن إزالة المالك الأصلي للروم أبداً.")
                            return

                        if len(self.owners) > 1:
                            self.owners.remove(original_owner)
                            self.save_config()
                            await self.highrise.chat(f"👑 تم إزالة @{original_owner} من قائمة الملاك")
                        else:
                            await self.highrise.send_whisper(user.id, "❌ لا يمكنك إزالة المالك الوحيد المتبقي!")
                    else:
                        await self.highrise.send_whisper(user.id, "❌ هذا المستخدم ليس مالكاً")
                else:
                    await self.highrise.send_whisper(user.id, "❌ مثال: ازالة_مالك أحمد")
                return
            
            elif command in ["owners", "الملاك"]:
                await self.highrise.chat(f"👑 الملاك الحاليين: {', '.join(self.owners)}")
                return
            
            elif command in ["reset", "ريست", "إعادة_تشغيل"]:
                self.muted_users.clear()
                self.frozen_users.clear()
                self.warned_users.clear()
                self.user_messages.clear()
                for user_id in list(self.dancing_users.keys()):
                    self.dancing_users[user_id].cancel()
                self.dancing_users.clear()
                
                # إعادة تحميل الإعدادات وإعادة البوت لمكانه
                self.load_config()
                try:
                    await self.highrise.teleport(self.highrise.my_id, self.bot_position)
                except: pass
                
                await self.highrise.chat("🔄 تم إعادة ضبط البوت، تحميل الإعدادات، والعودة للموقع المحفوظ! ✅")
                return

    async def show_help(self, user: User, conversation_id: str = None):
        """عرض قائمة المساعدة الذكية مع إجبار الرد في البريد الخاص (DM)"""
        if not conversation_id:
            try:
                # محاولة فتح محادثة جديدة لضمان ورود الرد في الخاص حتى لو طُلب من الروم
                conv = await self.highrise.create_conversation(user.id)
                conversation_id = conv.id
            except: pass
            
        is_owner = self.is_owner(user)
        is_admin = await self.is_admin(user)
        
        # تحديد الرتبة للترحيب المخصص
        role_name = "اللاعب"
        if is_owner: role_name = "المالك 👑"
        elif is_admin: role_name = "المشرف 🛡️"
        
        help_text = f"👋 مرحباً يا {role_name} @{user.username}! إليك الدليل الشامل للأوامر المسموحة لك:\n"

        common_commands = """
✨ أوامر اللاعبين العامة ✨
━━━━━━━━━━━━━━
📌 معلومات الغرفة والوقت:
/help 🔸 المساعدة الحالية
/وقت 🔸 عرض الوقت ⏰
/بحث @اسم 🔸 البحث عن يوزر 🔍
/المشرفين 🔸 عرض المشرفين 🛡️
/users 🔸 المتواجدين حالياً
/0 🔸 إيقاف الرقص والمرجحة
/احداثيات 🔸 موقعك 📍

🏢 أوامر التنقل:
ارضي / فوق / فوق2 / vip
(اكتب الكلمة فقط للانتقال فوراً)

🕺 الرقص والترفيه:
/رقصات 🔸 عرض الرقصات المتاحة
/رقصني 🔸 رقصة عشوائية 🎲
/0 لوب 🔸 لإيقاف تكرار الرقصة
/game 🔸 الألعاب المتاحة

🎭 التفاعلات (اكتب الاسم ثم @يوزر):
• قلب / بوس / حضن / غزل / ضحك
• لكم / ركل / كف / سحر / احترام
• طيران / تليبورت / قيتار / انمي
• تنويم / تسس 🐍 / زواج / خطبة
━━━━━━━━━━━━━━
"""

        admin_commands = """
🛡️ أوامر المشرفين 🛡️
━━━━━━━━━━━━━━
⚡ الرقابة والإدارة:
• طرد @اسم 🔸 طرد نهائي
• كتم / فك_كتم @اسم 🔸 إدارة الكلام
• حظر / فك_حظر @اسم 🔸 الدخول
• تحذير @اسم 🔸 تنبيه رسمي
• مسح 🔸 تنظيف الشات 🧹
• إعلان [الرسالة] 🔸 رسالة إدارية
• دعوة 🔸 إرسال دعوات للمتصلين 📨

📍 التحكم بالنظام والمستخدمين:
• جلب / سحب @اسم 🔸 إحضاره إليك
• روح @اسم 🔸 الذهاب له
• تجميد / فك_تجميد @اسم 🔸 تقييد الحركة
• مرجحة / إيقاف_مرجحة @اسم 🔸 المرجحة 🌪️
• نقل_الكل [موقع] 🔸 نقل جماعي
• تحت / فوق / vip @اسم 🔸 نقل لاعب
• تبديل @اسم1 @اسم2 🔸 تبديل مواقع
• نقل_موقع @اسم1 @اسم2 🔸 نقل لاعبين
• لبس / قلدني @اسم 🔸 نسخ ازياء 👗

💖 الفعاليات والإضافات:
• ر 🔸 إرسال قلوب للكل 💝
• اختصار <حرف> <@اسم> 🔸 قلب سريع
• تميز / الغاء_تميز @اسم 🔸 حماية
• قائمة_التميز 🔸 عرض المميزين 🛡️
━━━━━━━━━━━━━━
"""

        owner_commands = """
👑 أوامر الملاك 👑
━━━━━━━━━━━━━━
💰 المالية والذهب:
• جولد [اسم] [المبلغ] 🔸 إرسال ذهب 💰
• رصيد / محفظة 🔸 رصيد البوت الحالي

📍 إدارة الغرفة والمواقع:
• تعيين_طابق [موقع] 🔸 حفظ الطوابق
• هـنـا 🔸 تحديد موقع البوت
• سجادة [اسم] 🔸 حفظ منطقة رقص
• حذف_سجادة [اسم] 🔸 مسح منطقة
• ريست_طوابق 🔸 اعادة للافترضي
• نقل_سريع [نعم/لا] 🔸 النقل السريع

👋 إعدادات الترحيب:
• ترحيب [الرسالة] 🔸 تغيير الترحيب
• نوع_الترحيب 🔸 تبديل (همس/شات)
• ترحيب_خاص @اسم [رسالة] 🔸 للشخص
• حذف_ترحيب @اسم 🔸 مسح ترحيب خاص

🛡️ إدارة الطاقم:
• اضافة_مالك / ازالة_مالك @اسم
• الملاك 🔸 الملاك الحاليين
• اضف_مشرف / ازالة_مشرف @اسم
• اضف_vip / حذف_vip @اسم
• vip قائمة 🔸 استعراض الـ VIP

🔄 التحكم الشامل:
• لوب_رياكشن [رياكشن] @اسم 💝
• وقف_رياكشن 🔸 إيقاف
• ريست 🔸 تصفير البيانات واعادة التحميل
• reboot / off 🔸 إيقاف او اعاده تشغيل
━━━━━━━━━━━━━━
"""

        if is_owner:
            help_text += common_commands + admin_commands + owner_commands
        elif is_admin:
            help_text += common_commands + admin_commands
        else:
            help_text += common_commands

        await self.safe_send(user.id, help_text, conversation_id)
    async def is_admin(self, user: User) -> bool:
        """التحقق من صلاحيات المشرف"""
        if user.username.lower() in [o.lower() for o in self.owners]:
            return True
        
        if user.username.lower() in [a.lower() for a in self.admins if a]:
            return True
        
        try:
            permissions = await self.highrise.get_room_privilege(user.id)
            if not isinstance(permissions, Exception):
                return permissions.moderator or permissions.designer
        except:
            pass
        
        return False
    
    def is_owner(self, user: User) -> bool:
        """التحقق من المالك"""
        return user.username.lower() in [o.lower() for o in self.owners]

    async def can_moderate(self, caller: User, target: User) -> tuple[bool, str]:
        """التحقق مما إذا كان للشخص الحق في معاقبة الآخر"""
        # إذا كان المستدعي None فهذا يعني أن البوت هو من يقوم بالعملية تلقائياً (نظام)
        if caller is None:
            return True, ""
            
        caller_name = caller.username.lower()
        target_name = target.username.lower()
        is_caller_owner = self.is_owner(caller)
        
        # 1. المالك الأصلي للروم لديه حصانة ضد غير الملاك
        if self.room_owner_username and target_name == self.room_owner_username.lower():
            if not is_caller_owner:
                return False, "👑 المالك الأصلي للروم لديه حصانة كاملة!"
            return True, "" # الملاك يمكنهم التعامل معه (طلب المستخدم)
            
        # 2. الملاك يمكنهم معاقبة بعضهم (بناءً على طلب المستخدم)
        if self.is_owner(target):
            if not is_caller_owner:
                return False, "🛡️ لا يمكنك معاقبة الملاك! هذا حق للملاك فقط."
            return True, ""
            
        # 3. المشرفون محميون من المشرفين الآخرين واللاعبين
        if await self.is_admin(target):
            if not self.is_owner(caller):
                return False, "🛡️ المشرفون محميون! فقط الملاك يمكنهم معاقبتهم."
            return True, ""
            
        # 4. المميزون محميون من المشرفين واللاعبين (لكن ليس من الملاك)
        is_target_distinguished = target.username.lower() in [d.lower() for d in self.distinguished_users]
        if is_target_distinguished:
            if not self.is_owner(caller):
                return False, "🛡️ هذا المستخدم مميز ومحمي! فقط الملاك يمكنهم التعامل معه."
            return True, ""
            
        # 5. الجميع يمكنهم معاقبة اللاعبين العاديين
        return True, ""

    async def get_user_by_name(self, username: str) -> User | None:
        """الحصول على مستخدم من اسمه"""
        try:
            try:
                res = await self.highrise.get_room_users()
                users_list = getattr(res, 'content', [])
            except:
                users_list = []
                
            username_clean = username.strip()
            if username_clean.startswith('@'):
                username_clean = username_clean[1:]
            username_lower = username_clean.lower()
            
            for user, _ in users_list:
                if user.username.lower() == username_lower:
                    return user
            
            for user, _ in users_list:
                if username_lower in user.username.lower():
                    return user
                    
        except Exception as e:
            print(f"Error searching for user: {e}")
        
        return None

    async def kick_user(self, username: str, admin_user: User):
        """طرد مستخدم"""
        user = await self.get_user_by_name(username)
        if user:
            can_do, msg = await self.can_moderate(admin_user, user)
            if not can_do:
                await self.highrise.chat(f"❌ {msg}")
                return
            
            try:
                await self.highrise.moderate_room(user.id, "kick")
                await self.highrise.chat(f"👢 تم طرد {user.username}")
            except Exception as e:
                await self.highrise.chat(f"❌ خطأ: {e}")
        else:
            await self.highrise.chat(f"❌ لم يتم العثور على: {username}")

    async def ban_user(self, username: str, duration: int, admin_user: User):
        """حظر مستخدم"""
        user = await self.get_user_by_name(username)
        if user:
            can_do, msg = await self.can_moderate(admin_user, user)
            if not can_do:
                await self.highrise.chat(f"❌ {msg}")
                return
            try:
                await self.highrise.moderate_room(user.id, "ban", duration)
                await self.highrise.chat(f"🔨 تم حظر {username} لمدة {duration} ثانية")
            except Exception as e:
                await self.highrise.chat(f"❌ خطأ: {e}")
        else:
            await self.highrise.chat(f"❌ لم يتم العثور على: {username}")

    async def unban_user(self, username: str):
        """فك حظر مستخدم"""
        user = await self.get_user_by_name(username)
        if user:
            # ✅ لا يوجد إجراء "unban" في Highrise API
            # الحظر ينتهي تلقائياً بعد انتهاء المدة المحددة
            await self.highrise.chat(f"ℹ️ لا يمكن فك الحظر يدوياً - سينتهي تلقائياً. ({username})")
        else:
            await self.highrise.chat(f"❌ لم يتم العثور على: {username}")

    async def mute_user(self, username: str, duration: int, admin_user: User = None):
        """كتم مستخدم"""
        user = await self.get_user_by_name(username)
        if user:
            # التحقق من الصلاحيات إذا كان هناك مشرف (وليس كتم تلقائي)
            if admin_user:
                can_do, msg = await self.can_moderate(admin_user, user)
                if not can_do:
                    await self.highrise.chat(f"❌ {msg}")
                    return
            
            try:
                # 1. محاولة الكتم الرسمي عبر Highrise API (يمنع الرسائل من الظهور للكل)
                try:
                    await self.highrise.moderate_room(user.id, "mute", duration)
                    await self.highrise.chat(f"🔇 تم كتم {user.username} في الشات لمدة {duration} ثانية ✅")
                except Exception as e:
                    # 2. إذا فشل (البوت ليس مشرفاً)، نعتمد الكتم المحلي (البوت يطرده إذا تكلم)
                    await self.highrise.chat(f"🔇 تم كتم {user.username} محلياً (سيتم طرده إذا تكلم في الشات) 🛡️")
                    print(f"Server-side mute failed: {e}")
                
                # تخزين في القائمة المحلية للرقابة
                self.muted_users[user.id] = True
                await self.highrise.send_whisper(user.id, f"🔇 أنت مكتوم لمدة {duration} ثانية. (مسموح لك بالأوامر فقط، الدردشة العامة تعرضك للطرد)")
                
                async def auto_unmute():
                    await asyncio.sleep(duration)
                    if user.id in self.muted_users:
                        del self.muted_users[user.id]
                        try: await self.highrise.chat(f"🔊 انتهى وقت كتم {user.username}")
                        except: pass
                
                asyncio.create_task(auto_unmute())
                
            except Exception as e:
                await self.highrise.chat(f"❌ خطأ في الكتم: {e}")
        else:
            await self.highrise.chat(f"❌ لم يتم العثور على: {username}")

    async def unmute_user(self, username: str, admin_user: User):
        """فك كتم مستخدم"""
        user = await self.get_user_by_name(username)
        if user:
            # التحقق من الصلاحيات باستخدام النظام الموحد لتمكين الملاك من التعامل مع بعضهم
            can_do, msg = await self.can_moderate(admin_user, user)
            if not can_do:
                await self.highrise.chat(f"❌ {msg}")
                return
                
            try:
                # 1. محاولة فك الكتم عبر Highrise API (إذا كان مدعوماً)
                try:
                    await self.highrise.moderate_room(user.id, "mute", 1)  # تقليل المدة لثانية واحدة يعمل كفك كتم فعال
                    # أو إذا كان السكربت يدعم unmute صريحة:
                    # await self.highrise.moderate_room(user.id, "unmute")
                except: pass
                
                # 2. حذف المستخدم من قائمة المكتومين المحلية
                if user.id in self.muted_users:
                    del self.muted_users[user.id]
                    await self.highrise.chat(f"🔊 تم فك كتم {user.username} بنجاح ✅")
                else:
                    await self.highrise.chat(f"ℹ️ {user.username} لم يكن مكتوماً في قائمة البوت")
                    
            except Exception as e:
                print(f"General error in unmute: {e}")
                await self.highrise.chat(f"✅ تم محاولة فك كتم {username}")
        else:
            await self.highrise.chat(f"❌ لم يتم العثور على: {username}")

    async def warn_user(self, user: User, reason: str, admin_user: User = None):
        """تحذير مستخدم"""
        if admin_user:
            can_do, msg = await self.can_moderate(admin_user, user)
            if not can_do:
                await self.highrise.chat(f"❌ {msg}")
                return
        
        if user.id not in self.warned_users:
            self.warned_users[user.id] = 0
        
        self.warned_users[user.id] += 1
        warns = self.warned_users[user.id]
        
        await self.highrise.send_whisper(user.id, f"⚠️ تحذير ({warns}/3): {reason}")
        # البوت يرسل في الشات العام فقط إذا لم يكن تحذيراً "صامتاً"
        await self.highrise.chat(f"⚠️ تم تحذير {user.username} - السبب: {reason}")
        
        if warns >= 3:
            await self.highrise.chat(f"🔨 تم حظر {user.username} بسبب تجاوز التحذيرات")
            await self.highrise.moderate_room(user.id, "kick")
            del self.warned_users[user.id]

    async def is_begging(self, text: str) -> bool:
        """تحليل الرسالة لمعرفة ما إذا كانت تحتوي على شحادة حقيقية"""
        # 1. الأسئلة المشروعة (لا تعتبر شحادة)
        white_list = ["كيف", "طريقة", "شلون", "how", "وين", "where", "منين", "من وين"]
        if any(w in text for w in white_list):
            return False
            
        # 2. كلمات العملة
        currencies = ["ذهب", "جولد", "قولد", "كولد", "gold", "cold", "bar", "بارات", "بار"]
        found_currency = any(c in text for c in currencies)
        if not found_currency:
            return False

        # 3. محفزات الشحادة (Begging Triggers)
        # أفعال الطلب المباشرة
        actions = ["عطني", "اعطيني", "عطوني", "اعطوني", "جيب", "هات", "ارمي", "تبرع", "give", "donate", "drop", "toss"]
        # رغبات واحتياجات
        needs = ["ممكن", "ابي", "أبي", "بغيت", "محتاج", "مطفر", "اريد", "أريد", "بدي", "ارجوك", "please", "pls", "want", "need"]
        
        # فحص التركيب: فعل طلب + عملة في نفس الرسالة
        for action in actions:
            if action in text:
                return True
                
        # فحص التركيب: (ممكن/اريد/محتاج) + عملة (في رسالة قصيرة ومباشرة)
        if len(text.split()) <= 6:
            for need in needs:
                if need in text:
                    return True
        
        return False

    async def run_heartbeat(self):
        """نظام نبض القلب للتأكد من وجود البوت في الروم ومنع اختفائه"""
        while self.connection_active:
            try:
                # الانتظار 3 دقائق بين كل فحص
                await asyncio.sleep(180)
                
                if not self.connection_active: break
                
                # جلب قائمة المستخدمين للتحقق من وجود البوت
                res = await self.highrise.get_room_users()
                me_found = False
                if res and hasattr(res, 'content'):
                    for u, _ in res.content:
                        if u.id == self.highrise.my_id:
                            me_found = True
                            break
                
                if not me_found:
                    print(f"[{self.bot_name}] Heartbeat: البوت غير موجود في كشف الغرفة! جاري إعادة الانضمام...")
                    await self.highrise.teleport(self.highrise.my_id, self.bot_position)
                
                # إرسال رياكشن بسيط للحفاظ على "حرارة" الاتصال
                try:
                    await self.highrise.react("heart", self.highrise.my_id)
                except: pass
                
            except Exception as e:
                if "transport" in str(e).lower(): break
                await asyncio.sleep(10)

    async def list_users(self):
        """عرض قائمة المستخدمين"""
        try:
            room_users = await self.highrise.get_room_users()
            
            if getattr(room_users, 'content', []):
                user_list = []
                for i, (user, _) in enumerate(getattr(room_users, 'content', []), 1):
                    user_list.append(f"{i}. @{user.username}")
                
                users_str = "\n".join(user_list)
                await self.highrise.chat(f"👥 المستخدمين ({len(user_list)}):\n{users_str}")
            else:
                await self.highrise.chat("لا يوجد مستخدمين في الغرفة")
        except Exception as e:
            await self.highrise.chat(f"❌ خطأ: {e}")

    async def check_spam(self, user: User) -> bool:
        """فحص السبام"""
        import time
        
        if user.id not in self.user_messages:
            self.user_messages[user.id] = []
        
        current_time = time.time()
        self.user_messages[user.id].append(current_time)
        
        self.user_messages[user.id] = [
            t for t in self.user_messages[user.id] 
            if current_time - t < 10
        ]
        
        return len(self.user_messages[user.id]) > 15
    
    async def freeze_user(self, username: str, admin_user: User):
        """تجميد مستخدم"""
        user = await self.get_user_by_name(username)
        if user:
            can_do, msg = await self.can_moderate(admin_user, user)
            if not can_do:
                await self.highrise.chat(f"❌ {msg}")
                return
            
            try:
                room_users = await self.highrise.get_room_users()
                for u, pos in getattr(room_users, 'content', []):
                    if u.id == user.id:
                        self.frozen_users[user.id] = pos
                        await self.highrise.chat(f"🧊 تم تجميد {user.username}")
                        await self.highrise.send_whisper(user.id, "⚠️ تم تجميدك!")
                        return
                await self.highrise.chat(f"❌ لم يتم العثور على موقع {user.username}")
            except Exception as e:
                await self.highrise.chat(f"❌ خطأ: {e}")
        else:
            await self.highrise.chat(f"❌ لم يتم العثور على: {username}")
    
    async def unfreeze_user(self, username: str):
        """فك تجميد مستخدم"""
        user = await self.get_user_by_name(username)
        if user:
            if user.id in self.frozen_users:
                del self.frozen_users[user.id]
                await self.highrise.chat(f"✅ تم فك تجميد {username}")
                await self.highrise.send_whisper(user.id, "✅ تم فك تجميدك!")
            else:
                await self.highrise.chat(f"❌ {username} غير مجمد")
        else:
            await self.highrise.chat(f"❌ لم يتم العثور على: {username}")

    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem | Item) -> None:
        """عند استلام إكرامية - مع نظام التجميع الذكي للدفع"""
        try:
            self.interaction_history.add((sender.id, sender.username))
            
            if isinstance(tip, Item):
                item_str = f"{tip.amount}x {tip.id}" if tip.amount > 1 else tip.id
                await self.highrise.chat(f"🎁 شكراً {sender.username} على الهدية الرائعة ({item_str})! 🙏 😍")
                return

            if isinstance(tip, CurrencyItem):
                amount = tip.amount
                
                # إعداد الحصالة المؤقتة لهذا المستخدم
                if sender.id not in self._tip_buffer:
                    self._tip_buffer[sender.id] = {"amount": 0, "task": None}
                
                buffer = self._tip_buffer[sender.id]
                buffer["amount"] += amount
                
                # إلغاء المهمة السابقة إذا كانت موجودة (لتجديد الوقت)
                if buffer["task"]:
                    buffer["task"].cancel()
                
                # بدء عد تنازلي لانتظار باقي المبالغ (10 ثوانٍ)
                async def process_delayed_tip(uid=sender.id, uname=sender.username):
                    await asyncio.sleep(10)
                    try:
                        total = self._tip_buffer[uid]["amount"]
                        del self._tip_buffer[uid]
                        
                        days = 0
                        # حساب الأيام بناءً على أفضل العروض المتاحة للمجموع الكامل
                        if total >= 1500: 
                            months = total // 1500
                            days = months * 30
                            remainder = total % 1500
                            if remainder >= 1000: days += 15; remainder -= 1000
                            if remainder >= 500: days += 7; remainder -= 500
                            days += (remainder // 100)
                        elif total >= 1000: days = 15 + ((total - 1000) // 100)
                        elif total >= 500: days = 7 + ((total - 500) // 100)
                        else: days = total // 100
                        
                        if days > 0 and self.runner and hasattr(self.runner, 'db'):
                            new_time = self.runner.db.extend_expire(self.bot_name, days)
                            if new_time:
                                await self.highrise.chat(f"💰 تم استلام مجموع {total} جولد من @{uname}! تم تجديد الإيجار لـ {days} أيام إضافية 🚀")
                                await self.highrise.send_whisper(uid, f"✨ التجديد ناجح! المتبقي الإجمالي: {new_time}")
                                return

                        await self.highrise.chat(f"💰 شكراً @{uname} على {total} جولد! أنت كريم جداً 🙏")
                    except Exception as e: print(f"Tip buffer error: {e}")

                buffer["task"] = asyncio.create_task(process_delayed_tip())
                
        except Exception as e:
            print(f"Error processing tip: {e}")

    async def on_whisper(self, user: User, message: str) -> None:
        """عند استلام همس داخل الروم (Whisper)"""
        try:
            self.interaction_history.add((user.id, user.username))
            print(f"Whisper from {user.username}: {message}")
            await self.handle_command(user, message)
        except Exception as e:
            print(f"Error in on_whisper: {e}")
    async def on_envelope(self, user_id: str, message: str, conversation_id: str) -> None:
        """المعالج الأساسي لرسائل البريد الخاص (DM) - تم الإصلاح"""
        try:
            if user_id == self.bot_id: return
            
            # جلب الاسم من الذاكرة أو الغرفة أو الـ API
            username = self.cached_usernames.get(user_id, "User")
            if username == "User":
                try:
                    room_users = await self.highrise.get_room_users()
                    for u, _ in getattr(room_users, 'content', []):
                        if u.id == user_id:
                            username = u.username
                            self.cached_usernames[user_id] = username
                            break
                    if username == "User":
                        info = await self.highrise.get_user_info(user_id)
                        if hasattr(info, 'user'): 
                            username = info.user.username
                            self.cached_usernames[user_id] = username
                except: pass
            
            user = User(id=user_id, username=username)
            print(f"[{self.bot_name}] [DM Envelope] from {username}: {message}")
            self.interaction_history.add((user_id, username))
            
            await self.handle_command(user, message, conversation_id=conversation_id)
        except Exception as e:
            print(f"Error in on_envelope: {e}")

    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        """عند استلام رسالة في بريد البوت الخاص (Inbox)"""
        try:
            if user_id == self.bot_id: return
            res = await self.highrise.get_messages(conversation_id)
            messages = getattr(res, 'messages', getattr(res, 'content', []))
            
            if messages and len(messages) > 0:
                last_msg = messages[0]
                
                # جلب الاسم بشكل ذكي
                username = self.cached_usernames.get(user_id, "User")
                if username == "User":
                    try:
                        room_users = await self.highrise.get_room_users()
                        for u, _ in getattr(room_users, 'content', []):
                            if u.id == user_id:
                                username = u.username
                                self.cached_usernames[user_id] = username
                                break
                        if username == "User":
                            info = await self.highrise.get_user_info(user_id)
                            if hasattr(info, 'user'): 
                                username = info.user.username
                                self.cached_usernames[user_id] = username
                    except: pass
                
                print(f"[{self.bot_name}] [Inbox Message] from {username}: {last_msg.content}")
                user = User(id=user_id, username=username)
                await self.handle_command(user, last_msg.content, conversation_id=conversation_id)
        except Exception as e:
            print(f"Error in on_message: {e}")

    async def tip_user(self, sender: User, parts: list):
        """💰 نظام توزيع الجولد"""
        try:
            if len(parts) < 3:
                await self.safe_whisper(sender.id, "❌ مثال:\ntip اسم 100\ntip 5 50\ntip all 10")
                return

            # خريطة تحويل المبالغ إلى معرّفات جولد بار (Highrise Gold Bar IDs)
            tip_mapping = {
                1: "gold_bar_1", 5: "gold_bar_5", 10: "gold_bar_10",
                50: "gold_bar_50", 100: "gold_bar_100", 500: "gold_bar_500",
                1000: "gold_bar_1k", 5000: "gold_bar_5000", 10000: "gold_bar_10k"
            }

            if parts[1].lower() == "all":
                amount = int(parts[2])
                tip_id = tip_mapping.get(amount)
                if not tip_id:
                    await self.safe_whisper(sender.id, f"❌ المبلغ ({amount}) غير مدعوم. المبالغ المتاحة: 1، 5، 10، 50، 100، 500، 1000")
                    return

                try:
                    res = await self.highrise.get_room_users()
                    users_list = getattr(res, 'content', [])
                except:
                    users_list = []
                
                count = 0
                await self.safe_chat(f"💵 جاري توزيع {amount} جولد على الجميع...")
                
                for u, _ in users_list:
                    # تخطي البوت نفسه
                    if u.id == self.bot_id or u.id == self.highrise.my_id:
                        continue
                        
                    try:
                        await self.highrise.tip_user(u.id, tip_id)
                        count += 1
                        await asyncio.sleep(0.6) # تأخير طفيف للأمان
                    except Exception as e:
                        print(f"Tip error for {u.username}: {e}")
                
                await self.safe_chat(f"✅ تم توزيع {amount} جولد على {count} شخص!")
                return

            try:
                count_target = int(parts[1])
                amount = int(parts[2])
                tip_id = tip_mapping.get(amount)
                if not tip_id:
                    await self.safe_whisper(sender.id, f"❌ المبلغ ({amount}) غير مدعوم.")
                    return

                try:
                    res = await self.highrise.get_room_users()
                    all_users = getattr(res, 'content', [])
                except:
                    all_users = []
                
                users_list = [u for u, _ in all_users if u.id != self.bot_id and u.id != self.highrise.my_id]
                
                if not users_list:
                    await self.safe_whisper(sender.id, "❌ لا يوجد مستخدمين آخرين لتوزيع الجولد عليهم")
                    return

                import random
                selected = random.sample(users_list, min(count_target, len(users_list)))
                await self.safe_chat(f"💵 جاري إعطاء {amount} جولد لـ {len(selected)} أشخاص عشوائيين...")
                for u in selected:
                    try:
                        await self.highrise.tip_user(u.id, tip_id)
                        await asyncio.sleep(0.6)
                    except Exception as e:
                        print(f"Tip error: {e}")
                names = "، ".join([u.username for u in selected[:5]])
                await self.safe_chat(f"✅ تم إعطاء {amount} جولد لـ: {names}{'...' if len(selected) > 5 else ''}")
                return
            except ValueError:
                pass

            target_name = parts[1]
            amount = int(parts[2])
            tip_id = tip_mapping.get(amount)
            if not tip_id:
                await self.safe_whisper(sender.id, f"❌ المبلغ ({amount}) غير مدعوم.")
                return

            target_user = await self.get_user_by_name(target_name)
            if target_user:
                try:
                    await self.highrise.tip_user(target_user.id, tip_id)
                    await self.safe_chat(f"💵 تم إعطاء {amount} جولد لـ @{target_user.username}!")
                except Exception as e:
                    await self.safe_whisper(sender.id, f"❌ فشل الإرسال: {e}")
            else:
                await self.safe_whisper(sender.id, f"❌ لم يتم العثور على: {target_name}")

        except ValueError:
            await self.safe_whisper(sender.id, "❌ الرقم غير صحيح")
        except Exception as e:
            await self.safe_whisper(sender.id, f"❌ خطأ: {e}")

    async def send_invites(self, sender: User, custom_message: str = ""):
        """📨 إرسال دعوات للمتفاعلين"""
        try:
            if not self.interaction_history:
                await self.safe_whisper(sender.id, "❌ لا يوجد أشخاص في سجل التفاعلات بعد")
                return
            invite_msg = custom_message if custom_message else "🌟 مرحباً! البوت يدعوك للانضمام إلى الروم!"
            await self.safe_whisper(sender.id, f"📨 جاري إرسال دعوات لـ {len(self.interaction_history)} شخص...")
            sent = 0
            for user_id, username in list(self.interaction_history):
                try:
                    await self.highrise.send_whisper(user_id, invite_msg)
                    sent += 1
                    await asyncio.sleep(1.0) # زيادة التأخير للأمان
                except Exception as e:
                    print(f"Invite error for {username}: {e}")
            await self.safe_whisper(sender.id, f"✅ تم إرسال الدعوة لـ {sent} شخص!")
        except Exception as e:
            await self.safe_whisper(sender.id, f"❌ خطأ: {e}")

    async def equip_bot_from_user(self, sender: User, target_username: str):
        """👗 نسخ ملابس مستخدم آخر"""
        try:
            target_user = await self.get_user_by_name(target_username)
            if not target_user:
                await self.safe_whisper(sender.id, f"❌ لم يتم العثور على: {target_username}")
                return
            await self.safe_whisper(sender.id, f"👗 جاري نسخ ملابس {target_user.username}...")
            user_outfit = await self.highrise.get_user_outfit(target_user.id)
            if user_outfit and hasattr(user_outfit, 'outfit'):
                # حفظ الملابس الجديدة
                self.outfit = user_outfit.outfit
                self.save_config()
                
                await self.highrise.set_outfit(user_outfit.outfit)
                await self.safe_chat(f"👗 البوت يرتدي الآن ملابس {target_user.username} (وتم حفظها كزي رسمي)!")
            else:
                await self.safe_whisper(sender.id, "❌ لم أتمكن من جلب ملابس هذا المستخدم")
        except Exception as e:
            await self.safe_whisper(sender.id, f"❌ خطأ: {e}")

    async def switch_positions(self, requester: User, target_username: str):
        """🔄 تبديل موقع المشرف مع مستخدم"""
        try:
            target_user = await self.get_user_by_name(target_username)
            if not target_user:
                await self.safe_whisper(requester.id, f"❌ لم يتم العثور على: {target_username}")
                return
            # حماية الملاك والمشرفين بنظام can_moderate
            can_do, msg = await self.can_moderate(requester, target_user)
            if not can_do:
                await self.safe_whisper(requester.id, f"❌ {msg}")
                return

            room_users = await self.highrise.get_room_users()
            req_pos = next((pos for u, pos in getattr(room_users, 'content', []) if u.id == requester.id), None)
            target_pos = next((pos for u, pos in getattr(room_users, 'content', []) if u.id == target_user.id), None)
            if req_pos and target_pos and isinstance(req_pos, Position) and isinstance(target_pos, Position):
                await asyncio.gather(
                    self.highrise.teleport(requester.id, target_pos),
                    self.highrise.teleport(target_user.id, req_pos)
                )
                await self.safe_chat(f"🔄 تم تبديل موقع {requester.username} مع {target_user.username}!")
            else:
                await self.safe_whisper(requester.id, "❌ لم أتمكن من جلب المواقع")
        except Exception as e:
            await self.safe_whisper(requester.id, f"❌ خطأ: {e}")

    async def move_users(self, requester: User, user1_name: str, user2_name: str):
        """🔄 تبديل مواقع مستخدمين"""
        try:
            user1 = await self.get_user_by_name(user1_name)
            user2 = await self.get_user_by_name(user2_name)
            if not user1 or not user2:
                await self.safe_whisper(requester.id, "❌ لم يتم العثور على أحد المستخدمين")
                return
            # حماية الملاك والمشرفين باستخدام can_moderate لكل مستخدم
            can_do1, msg1 = await self.can_moderate(requester, user1)
            can_do2, msg2 = await self.can_moderate(requester, user2)
            
            if not can_do1:
                await self.safe_whisper(requester.id, f"❌ {msg1} (@{user1.username})")
                return
            if not can_do2:
                await self.safe_whisper(requester.id, f"❌ {msg2} (@{user2.username})")
                return

            room_users = await self.highrise.get_room_users()
            pos1 = next((pos for u, pos in getattr(room_users, 'content', []) if u.id == user1.id), None)
            pos2 = next((pos for u, pos in getattr(room_users, 'content', []) if u.id == user2.id), None)
            if pos1 and pos2 and isinstance(pos1, Position) and isinstance(pos2, Position):
                await asyncio.gather(
                    self.highrise.teleport(user1.id, pos2),
                    self.highrise.teleport(user2.id, pos1)
                )
                await self.safe_chat(f"🔄 تم تبديل موقع {user1.username} مع {user2.username}!")
            else:
                await self.safe_whisper(requester.id, "❌ لم أتمكن من جلب المواقع")
        except Exception as e:
            await self.safe_whisper(requester.id, f"❌ خطأ: {e}")
    # ... نهاية الكود الرئيسي ...
    pass

# ═══════════════════════════════════════════════════════════════
# قاعدة بيانات الغرف والمانجر
# ═══════════════════════════════════════════════════════════════

ROOMS_FILE = BASE_DIR / "rooms_db.json"

class RoomsDB:
    def __init__(self):
        self.rooms: dict = {}
        if ROOMS_FILE.exists():
            try: 
                self.rooms = json.loads(ROOMS_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                bak_file = ROOMS_FILE.with_name(ROOMS_FILE.name + '.bak')
                if bak_file.exists():
                    try: self.rooms = json.loads(bak_file.read_text(encoding="utf-8"))
                    except: pass
            except: pass

    def _save(self):
        try:
            temp_file = ROOMS_FILE.with_name(ROOMS_FILE.name + '.tmp')
            bak_file = ROOMS_FILE.with_name(ROOMS_FILE.name + '.bak')
            temp_file.write_text(json.dumps(self.rooms, ensure_ascii=False, indent=2), encoding="utf-8")
            
            if ROOMS_FILE.exists():
                import shutil
                try: shutil.copy2(ROOMS_FILE, bak_file)
                except: pass
                
            temp_file.replace(ROOMS_FILE)
        except Exception as e:
            print(f"⚠️ خطأ في حفظ قاعدة البيانات (rooms_db): {e}")
            if "No space left" in str(e) or "Errno 28" in str(e):
                print("🚨 تنبيه: القرص ممتلئ! يرجى مسح الملفات الزائدة أو ملفات الـ log الكبيرة على السيرفر.")

    def add(self, name, token, room_id, days=None) -> str:
        if name in self.rooms:
            return f"⚠️ '{name}' موجود بالفعل"
        expire = None
        if days:
            try:
                days_float = float(days)
                expire = (datetime.now() + timedelta(days=days_float)).isoformat()
            except ValueError:
                return "❌ خطأ: مدة الإيجار ليست صالحة"
        self.rooms[name] = {"name": name, "token": token, "room_id": room_id, "expire": expire}
        self._save()
        self._init_config(name)
        exp_str = f" (ينتهي بعد {days} يوم)" if days else ""
        return f"✅ تمت إضافة البوت '{name}' للروم{exp_str}"

    def remove(self, name) -> str:
        if name not in self.rooms: return f"❌ بوت '{name}' غير موجود"
        del self.rooms[name]; self._save()
        return f"🗑️ تم حذف بيانات '{name}'"

    def get(self, name): return self.rooms.get(name)
    def all_names(self): return list(self.rooms.keys())

    def _config_path(self, name):
        name_clean = name.lstrip("@").lower()
        return BASE_DIR / f"bot_config_{name_clean}.json"

    def _init_config(self, name):
        p = self._config_path(name)
        if p.exists(): return
        temp_p = p.with_name(p.name + '.tmp')
        try:
            temp_p.write_text(json.dumps({
                "welcome_message": "رسالة الترحيب الافتراضية", "welcome_public": True,
                "owners": [], "admins": [], "vip_users": [],
                "distinguished_users": [], "custom_welcomes": {},
                "bot_position": {"x": 9.5, "y": 0.0, "z": 14.5, "facing": "FrontLeft"},
                "floors": {
                    "ground": {"x": 9.5, "y": 0.0, "z": 14.5, "facing": "FrontLeft"},
                    "floor1": {"x": 14.5, "y": 7.5, "z": 13.5, "facing": "FrontLeft"},
                    "floor2": {"x": 15.5, "y": 13.75, "z": 6.5, "facing": "FrontRight"},
                    "vip":    {"x": 12.0, "y": 13.75, "z": 0.5, "facing": "FrontLeft"},
                },
                "carpets": [],
                "banned_words": [], "auto_mod": True, 
                "begging_protection": True, "insult_protection": True,
                "spam_protection": True,
                "smart_teleport": True,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_p.replace(p)
        except Exception as e:
            print(f"⚠️ فشل إنشاء ملف الإعدادات لـ {name}: {e}")

    def load_config(self, name) -> dict:
        p = self._config_path(name)
        if not p.exists(): self._init_config(name)
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            bak_p = p.with_name(p.name + '.bak')
            if bak_p.exists():
                try: return json.loads(bak_p.read_text(encoding="utf-8"))
                except: pass
            return {}

    def save_config(self, name, cfg):
        p = self._config_path(name)
        temp_p = p.with_name(p.name + '.tmp')
        bak_p = p.with_name(p.name + '.bak')
        try:
            temp_p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            
            if p.exists():
                import shutil
                try: shutil.copy2(p, bak_p)
                except: pass
                
            temp_p.replace(p)
        except Exception as e:
            print(f"⚠️ فشل حفظ إعدادات {name}: {e}")

    def check_expired(self, name) -> bool:
        room = self.get(name)
        if not room or not room.get("expire"): return False
        return datetime.now() > datetime.fromisoformat(room["expire"])

    def remaining_days(self, name) -> str:
        room = self.get(name)
        if not room or not room.get("expire"): return "بلا حد"
        delta = datetime.fromisoformat(room["expire"]) - datetime.now()
        if delta.total_seconds() <= 0: return "منتهي ⛔"
        d = delta.days
        h = delta.seconds // 3600
        return f"{d} يوم و {h} ساعة"

    def set_expire(self, name, days):
        room = self.get(name)
        if not room: return
        room["expire"] = (datetime.now() + timedelta(days=float(days))).isoformat()
        self._save()

    def extend_expire(self, name, days) -> str:
        """تمديد الإيجار بشكل تراكمي (إضافة أيام للمدة الحالية)"""
        room = self.get(name)
        if not room: return None
        
        # إذا كان البوت منتهي أو جديد، ابدأ من الآن
        if not room.get("expire") or self.check_expired(name):
            start_date = datetime.now()
        else:
            # إذا كان لسا فيه وقت، زيد عليه
            start_date = datetime.fromisoformat(room["expire"])
            
        new_expire = start_date + timedelta(days=float(days))
        room["expire"] = new_expire.isoformat()
        self._save()
        return self.remaining_days(name)


class BotRunner:
    def __init__(self, db: RoomsDB):
        self.db = db
        self.tasks: dict[str, asyncio.Task] = {}
        self.instances: dict[str, object] = {}

    async def start(self, name, manager_owner=None) -> str:
        if self.db.check_expired(name):
            return f"⛔ '{name}' انتهت مدة الإيجار"
        room = self.db.get(name)
        if not room: return f"❌ '{name}' غير موجود"
        if name in self.tasks and not self.tasks[name].done():
            return f"⚠️ '{name}' يعمل بالفعل 🟢"
        
        if manager_owner:
            os.environ[f"BOT_RENTER_{room['room_id']}"] = manager_owner
            
        self.tasks[name] = asyncio.create_task(
            self._run(name, room["token"], room["room_id"]), name=f"bot-{name}"
        )
        return f"▶️ جاري تشغيل '{name}'..."

    async def _run(self, name, token, room_id):
        while True:
            try:
                if self.db.check_expired(name):
                    print(f"[{name}] ⛔ الإيجار منتهي.")
                    break
                bot = MyBot(room_id=room_id, runner=self, bot_name=name)
                self.instances[name] = bot
                print(f"[{name}] 🟢 متصل")
                await hr_main([BotDefinition(bot, room_id, token)])
                if getattr(bot, "should_stop", False): break
            except asyncio.CancelledError: break
            except Exception as e:
                err_msg = str(e)
                if "designer rights" in err_msg.lower() or "invited" in err_msg.lower():
                    print(f"[{name}] ❌ خطأ صلاحيات: البوت لا يملك صلاحية دخول الروم {room_id}!")
                    print(f"[{name}] 💡 الحل: تأكد أن البوت يملك Designer Rights في هذه الغرفة.")
                    # نتوقف عن المحاولة المتكررة لهذا البوت تحديداً لتجنب استهلاك الموارد
                    break
                else:
                    print(f"[{name}] ❌ خطأ: {e} — إعادة الاتصال خلال 10ث...")
                    await asyncio.sleep(10)
        self.instances.pop(name, None)

    async def stop(self, name) -> str:
        task = self.tasks.get(name)
        if not task or task.done(): return f"⚠️ البوت '{name}' غير متصل"
        bot = self.instances.get(name)
        if bot:
            bot.should_stop = True
            bot.connection_active = False
            bot.bot_dancing = False
        task.cancel()
        try: await asyncio.wait_for(asyncio.shield(task), timeout=3)
        except: pass
        self.tasks.pop(name, None)
        return f"🛑 تم إيقاف '{name}'"

    async def reboot(self, name):
        """إعادة تشغيل بوت معين"""
        print(f"[{name}] 🔄 جاري إعادة التشغيل...")
        await self.stop(name)
        await asyncio.sleep(5)
        return await self.start(name)

    async def start_all(self, manager_owner=None) -> list:
        results = []
        for name in self.db.all_names():
            results.append(await self.start(name, manager_owner))
            await asyncio.sleep(2)
        return results

    async def stop_all(self) -> list:
        results = []
        for name in list(self.tasks.keys()):
            results.append(await self.stop(name))
        return results

    def is_running(self, name) -> bool:
        t = self.tasks.get(name)
        return bool(t and not t.done())

    def status_all(self) -> list:
        return [
            {
                "name": n,
                "running": self.is_running(n),
                "room_id": self.db.get(n)["room_id"],
                "remaining": self.db.remaining_days(n)
            }
            for n in self.db.all_names()
        ]


class ManagerBot(BaseBot):
    PREFIX = ("بوت", "bot")

    def __init__(self, db: RoomsDB, runner: BotRunner, owner: str):
        super().__init__()
        self.db     = db
        self.runner = runner
        self.owner  = owner.lower() if owner else ""
        self.auto_started = False  # لمنع تكرار التشغيل عند إعادة اتصال المانجر نفسه

    async def on_start(self, session_metadata: SessionMetadata):
        print(f"🤖 بوت الإدارة/المانجر متصل | {session_metadata.room_info.room_name}")
        
        # حجز الصلاحية الاستثنائية لليوزر الأساسي
        if not self.owner:
            print("لم يتم تحديد مالك للمانجر، سيتم اعتماد أول شخص يستخدمه!")
            
        if not self.auto_started:
            self.auto_started = True
            names = self.db.all_names()
            if names:
                print(f"📋 {len(names)} رومات تم تأجيرها — جاري التشغيل التلقائي...")
                await asyncio.sleep(3)
                for msg in await self.runner.start_all(self.owner):
                    print(f"  {msg}")

    async def on_user_join(self, user: User, position: Position):
        """ترحيب مخصص في المانجر بناءً على حالة المستخدم"""
        if user.id == self.highrise.my_id: return
        
        # فحص إذا كان المستخدم مسجل كصاحب بوت
        bot_name = self._find_bot_match(user.username)
        
        if bot_name:
            # ترحيب بالزبون الحالي
            remaining = self.db.remaining_days(bot_name)
            await self.highrise.chat(f"👋 أهلاً بك يا غالي @{user.username}! ✨\nنورت مركز الإدارة. لعملائنا الكرام: اشتراكك [{bot_name}] متبقي فيه: {remaining}")
        else:
            # ترحيب بلاعب جديد مهتم بالاستئجار
            await self.highrise.chat(f"🏷️ أهلاً بك @{user.username} في مركز إدارة البوتات! 🤖\n✨ إذا أردت استئجار بوت لغرفتك (حماية/ذكاء اصطناعي/إدارة)، يرجى مراسلة المطور @NMR0")
            await self.highrise.send_whisper(user.id, "💡 نوفر لك أسرع وأذكى البوتات في اللعبة.")

    async def on_chat(self, user: User, message: str):
        if not self.owner:
             self.owner = user.username.lower()
             await self.highrise.chat(f"👑 تم تعيين @{self.owner} كصاحب لوحة التحكم الأساسي!")
             
        p = message.strip().split(maxsplit=1)
        if not p or p[0].lower() not in self.PREFIX: return
        
        # استخراج الأمر للتحقق من الصلاحية
        cmd_part = p[1].strip().split() if len(p) > 1 else []
        cmd_name = cmd_part[0].lower() if cmd_part else ""
        
        # يسمح للجميع بـ mybot، أما باقي الأوامر للمالك فقط
        if user.username.lower() != self.owner and cmd_name != "mybot":
            return
            
        await self._handle(user, p[1] if len(p) > 1 else "help")

    async def on_whisper(self, user: User, message: str):
        # في الهمس، نسمح بـ mybot للجميع أيضاً
        p = message.strip().split()
        cmd_name = p[0].lower() if p else ""
        if self.owner and user.username.lower() != self.owner and cmd_name != "mybot":
            return
        await self._handle(user, message)

    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem | Item) -> None:
        """نظام تجديد الإيجار الآلي في المانجر مع دعم التجميع"""
        if receiver.id != self.highrise.my_id: return
        if not isinstance(tip, CurrencyItem): return
        
        amount = tip.amount
        
        if not hasattr(self, '_tip_buffer'): self._tip_buffer = {}
        
        if sender.id not in self._tip_buffer:
            self._tip_buffer[sender.id] = {"amount": 0, "task": None}
        
        buffer = self._tip_buffer[sender.id]
        buffer["amount"] += amount
        
        if buffer["task"]: buffer["task"].cancel()

        async def process_manager_tip(uid=sender.id, uname=sender.username):
            await asyncio.sleep(10)
            try:
                total = self._tip_buffer[uid]["amount"]
                del self._tip_buffer[uid]
                
                days = 0
                if total >= 1500: 
                    days = (total // 1500) * 30
                    remainder = total % 1500
                    if remainder >= 1000: days += 15; remainder -= 1000
                    if remainder >= 500: days += 7; remainder -= 500
                    days += (remainder // 100)
                elif total >= 1000: days = 15 + ((total - 1000) // 100)
                elif total >= 500: days = 7 + ((total - 500) // 100)
                else: days = total // 100
                
                if days > 0:
                    bot_name = self._find_bot_match(uname)
                    if bot_name:
                        new_time = self.db.extend_expire(bot_name, days)
                        await self.highrise.chat(f"💰 مجموع ما وصل من @{uname} هو {total}! تم تمديد [{bot_name}] لـ {days} أيام إضافية ✅")
                        await self.highrise.send_whisper(uid, f"✨ تم التجديد! المتبقي: {new_time}")
                        
                        # إذا كان البوت متوقف، نقوم بتشغيله تلقائياً بعد التجديد
                        if not self.runner.is_running(bot_name):
                            await self.runner.start(bot_name, self.owner)
                            await self.highrise.chat(f"🚀 تم إعادة تشغيل البوت [{bot_name}] تلقائياً!")
                    else:
                        await self.highrise.chat(f"💰 مجموع ما وصل {total} جولد من @{uname}! (لم أجد بوتك، كلم المطور) ⚠️")
                else:
                    await self.highrise.chat(f"💝 شكراً @{uname} على الهدية! ({total} جولد)")
            except Exception as e: print(f"Manager tip error: {e}")

        buffer["task"] = asyncio.create_task(process_manager_tip())

    def _find_bot_match(self, query: str) -> str:
        """بحث ذكي عن اسم البوت (تجاهل حالة الأحرف وبحث جزئي)"""
        if not query: return None
        query = query.lower().lstrip("@")
        all_names = self.db.all_names()
        
        # 1. بحث عن تطابق تام (تجاهل حالة الأحرف)
        for name in all_names:
            if name.lower() == query:
                return name
                
        # 2. بحث عن تطابق جزئي
        matches = [name for name in all_names if query in name.lower()]
        if len(matches) >= 1:
            # إذا وجد أكثر من واحد، نفضل الأقصر (الأقرب للكلمة)
            return sorted(matches, key=len)[0]
            
        return None

    async def _handle(self, user: User, text: str):
        p   = text.strip().split(maxsplit=5)
        cmd = p[0].lower() if p else "help"

        if cmd in ("help", "مساعدة", "?"):
            await self._w(user,
                "📋 أوامر بوت الإدارة المركزي:\n"
                "بوت add <الاسم> <التوكن> <روم_ايدي> [أيام الإيجار]\n"
                "بوت start <الاسم> [أيام] | all\n"
                "بوت stop  <الاسم | all>\n"
                "بوت list - لرؤية الرومات\n"
                "بوت وقت <الاسم> - لمعرفة المتبقي\n"
                "بوت إيجار <الاسم> <أيام> - زيادة المدة\n"
                "بوت config <الاسم> - عرض إعدادات\n"
                "بوت remove <الاسم>\n\n"
                "── أوامر النيابة ──\n"
                "بوت owner <الاسم> <يوزر> - إضافة مالك\n"
                "بوت admin <الاسم> <يوزر> - مشرف\n"
                "بوت welcome <الاسم> <رسالة>\n"
                "بوت floor <الاسم> <طابق> <x> <y> <z>"
            )

        elif cmd == "add":
            if len(p) < 4:
                await self._w(user, "❌ للصيغة: بوت add اسم_العميل التوكن الروم_آيدي الأيام\nمثال: بوت add VIPTOKEN ROOMID 30")
            else:
                days = p[4] if len(p) > 4 else None
                await self._w(user, self.db.add(p[1], p[2], p[3], days))

        elif cmd == "remove":
            if len(p) < 2: await self._w(user, "❌ مثال: بوت remove الاسم")
            else:
                name = self._find_bot_match(p[1])
                if not name: await self._w(user, f"❌ العميل [{p[1]}] غير موجود"); return
                if self.runner.is_running(name): await self._w(user, await self.runner.stop(name))
                await self._w(user, self.db.remove(name))

        elif cmd == "list":
            statuses = self.runner.status_all()
            if not statuses:
                await self._w(user, "📋 لا توجد بوتات حالياً\nاستخدم: بوت add <الاسم> <توكن> <روم>")
                return
            lines = ["📊 حالة البوتات (عقود الإيجار):"]
            for s in statuses:
                icon = "🟢" if s["running"] else "🔴"
                lines.append(f"{icon} عميل: {s['name']} | ⏳ المتبقي: {s['remaining']}")
            total   = len(statuses)
            running = sum(1 for s in statuses if s["running"])
            lines.append(f"─\nالمجموع: {total} | تعمل: {running} | متوقفة: {total-running}")
            await self._w(user, "\n".join(lines))

        elif cmd == "start":
            if len(p) < 2: await self._w(user, "❌ مثال: بوت start الاسم  أو  بوت start all")
            elif p[1].lower() == "all":
                results = await self.runner.start_all(self.owner)
                await self._w(user, "\n".join(results) or "لا توجد بوتات محفوظة")
            else:
                name = self._find_bot_match(p[1])
                if not name: await self._w(user, f"❌ العميل [{p[1]}] غير موجود"); return
                if len(p) > 2:
                    try:
                        days = float(p[2])
                        self.db.set_expire(name, days)
                        await self._w(user, f"⏳ تم ضبط إيجار [{name}] لـ {days} يوم")
                    except: pass
                await self._w(user, await self.runner.start(name, self.owner))

        elif cmd == "stop":
            if len(p) < 2: await self._w(user, "❌ مثال: بوت stop الاسم  أو  بوت stop all")
            elif p[1].lower() == "all":
                results = await self.runner.stop_all()
                await self._w(user, "\n".join(results) or "لا يوجد بوتات شغالة")
            else:
                name = self._find_bot_match(p[1])
                if not name: await self._w(user, f"❌ العميل [{p[1]}] غير موجود"); return
                await self._w(user, await self.runner.stop(name))

        elif cmd in ("إيجار", "rent"):
            if len(p) < 3:
                await self._w(user, "❌ مثال: بوت إيجار اسم_العميل 30")
                return
            name = self._find_bot_match(p[1])
            if not name: await self._w(user, f"❌ العميل [{p[1]}] غير موجود"); return
            days = p[2]
            try:
                d = float(days)
                self.db.set_expire(name, d)
                remaining = self.db.remaining_days(name)
                await self._w(user, f"✅ [{name}] تم تمديد الإيجار بنجاح\n⏳ المتبقي: {remaining}")
            except ValueError:
                await self._w(user, "❌ الأيام يجب أن تكون أرقام صحيحة")

        elif cmd == "welcome":
            if len(p) < 3: await self._w(user, "❌ مثال: بوت welcome خالد مرحباً! 🍂"); return
            name = self._find_bot_match(p[1])
            if not name: await self._w(user, f"❌ العميل [{p[1]}] غير موجود"); return
            msg = " ".join(p[2:])
            cfg = self.db.load_config(name); cfg["welcome_message"] = msg
            self.db.save_config(name, cfg)
            bot = self.runner.instances.get(name)
            if bot: bot.welcome_message = msg
            await self._w(user, f"✅ [{name}] الترحيب الكلي أصبح:\n'{msg}'")

        elif cmd == "owner":
            if len(p) < 3: await self._w(user, "❌ مثال: بوت owner خالد y_7x"); return
            name = self._find_bot_match(p[1])
            if not name: await self._w(user, f"❌ العميل [{p[1]}] غير موجود"); return
            uname = p[2].lstrip("@")
            cfg = self.db.load_config(name)
            owners = cfg.setdefault("owners", [])
            if uname.lower() in [o.lower() for o in owners]:
                await self._w(user, f"⚠️ @{uname} مالك بالفعل لـ [{name}]"); return
            owners.append(uname); self.db.save_config(name, cfg)
            bot = self.runner.instances.get(name)
            if bot: bot.owners = owners
            await self._w(user, f"✅ [{name}] تمت إضافة @{uname} كمالك 👑")

        elif cmd == "admin":
            if len(p) < 3: await self._w(user, "❌ مثال: بوت admin خالد v.1n"); return
            name = self._find_bot_match(p[1])
            if not name: await self._w(user, f"❌ العميل [{p[1]}] غير موجود"); return
            uname = p[2].lstrip("@")
            cfg = self.db.load_config(name)
            admins = cfg.setdefault("admins", [])
            if uname.lower() in [a.lower() for a in admins]:
                await self._w(user, f"⚠️ @{uname} مشرف بالفعل لـ [{name}]"); return
            admins.append(uname); self.db.save_config(name, cfg)
            bot = self.runner.instances.get(name)
            if bot: bot.admins = admins
            await self._w(user, f"✅ [{name}] تمت إضافة @{uname} كمشرف 🛡️")

        elif cmd == "floor":
            ap = text.split()
            if len(ap) < 6:
                await self._w(user, "❌ لتغيير الإحداثيات للطلبات الخارجية:\nبوت floor عميل vip 12.0 13.75 0.5\n(يفضل أن يضبطها صاحب الروم داخلياً)")
                return
            name, floor = ap[1], ap[2]
            if floor not in {"ground", "floor1", "floor2", "vip"}:
                await self._w(user, "❌ الطوابق المسموحة للتحكم الخارجي: ground / floor1 / floor2 / vip"); return
            try:
                x, y, z = float(ap[3]), float(ap[4]), float(ap[5])
                facing  = ap[6] if len(ap) > 6 else "FrontLeft"
                cfg     = self.db.load_config(name)
                cfg.setdefault("floors", {})[floor] = {"x": x, "y": y, "z": z, "facing": facing}
                self.db.save_config(name, cfg)
                bot = self.runner.instances.get(name)
                if bot: bot.floors[floor] = Position(x, y, z, facing)
                await self._w(user, f"✅ [{name}] {floor} تم ضبطه عن بعد.")
            except ValueError:
                await self._w(user, "❌ أرقام غير صحيحة")

        elif cmd == "config":
            if len(p) < 2: await self._w(user, "❌ مثال: بوت config الاسم"); return
            name = self._find_bot_match(p[1])
            if not name: await self._w(user, f"❌ العميل [{p[1]}] غير مسجل أو الاسم غير دقيق"); return
            cfg  = self.db.load_config(name)
            lines = [
                f"⚙️ إعدادات عميل: [{name}]",
                f"🟢 الحالة: {'يعمل' if self.runner.is_running(name) else 'متوقف'}",
                f"⏳ الإيجار: {self.db.remaining_days(name)}",
                f"📢 الترحيب: {cfg.get('welcome_message','غير محدد')}",
                f"👑 الملاك: {', '.join(cfg.get('owners',[])) or 'لا يوجد'}",
                f"🛡️ المشرفون: {', '.join(cfg.get('admins',[])) or 'لا يوجد'}"
            ]
            await self._w(user, "\n".join(lines))

        elif cmd in ("وقت", "مدة", "time", "إيجار_باقي"):
            if len(p) < 2: await self._w(user, "❌ مثال: بوت وقت خالد")
            else:
                name = self._find_bot_match(p[1])
                if not name: await self._w(user, f"❌ العميل [{p[1]}] غير مسجل")
                else: await self._w(user, f"⏳ المتبقي لعميل [{name}]: {self.db.remaining_days(name)}")

        elif cmd == "mybot":
            # البحث عن بوت يحمل اسم المستخدم أو جزء منه
            target = p[1] if len(p) > 1 else user.username
            name = self._find_bot_match(target)
            if not name:
                await self._w(user, f"❓ لم أجد بوت مسجل باسم @{target}")
            else:
                remaining = self.db.remaining_days(name)
                status = "🟢 يعمل" if self.runner.is_running(name) else "🔴 متوقف"
                await self._w(user, f"📦 بوتك المسجل: [{name}]\n📊 الحالة: {status}\n⏳ المتبقي: {remaining}")

        else:
            await self._w(user, f"❓ طلب مرفوض\nاكتب: بوت help")

    async def _w(self, user: User, text: str):
        try:
            for chunk in [text[i:i+240] for i in range(0, len(text), 240)]:
                await self.highrise.send_whisper(user.id, chunk)
                await asyncio.sleep(0.2)
        except Exception as e:
            pass


if __name__ == "__main__":
    # ===== إعدادات لوحة التحكم (Manager) =====
    MANAGER_ROOM_ID = "68f40a7076bde792332841e5"
    MANAGER_TOKEN = "faf56f6606d5d914cc27969d4b8f6dbd06a6ea348e049d729969abe2fbd5901d"
    # إذا تركتها فارغة سيتم اعتبار أول من يرسل رسالة في الروم هو المالك الوحيد
    OWNER_USERNAME = "NMR0"  
    # =========================================

    async def run_manager():
        db = RoomsDB()
        runner = BotRunner(db)
        manager = ManagerBot(db, runner, OWNER_USERNAME)

        print("=" * 60)
        print("  🤖 تم تشغيل نظام بوت الإدارة المركزي (المانجر)")
        print(f"  🏢 الغرفة الحالية: {MANAGER_ROOM_ID}")
        print("=" * 60)
        
        try:
            while True:
                try:
                    await hr_main([BotDefinition(manager, MANAGER_ROOM_ID, MANAGER_TOKEN)])
                    if getattr(manager, 'should_stop', False):
                        break
                except (Exception, asyncio.CancelledError) as e:
                    if isinstance(e, asyncio.CancelledError): raise
                    print(f"Manager error: {e}. Restarting in 10s...")
                    await asyncio.sleep(10)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n🛑 جاري إيقاف جميع البوتات والمانجر...")
        finally:
            # إغلاق كل البوتات الشغالة قبل الخروج النهائي
            results = await runner.stop_all()
            for res in results: print(f"  {res}")
            print("👋 تم إغلاق النظام بالكامل.")

    try:
        asyncio.run(run_manager())
    except KeyboardInterrupt:
        pass