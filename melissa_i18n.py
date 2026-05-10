#!/usr/bin/env python3
"""
melissa_i18n.py — Multilingual support for Melissa
Supported languages: es, en, pt, fr, de
"""

from __future__ import annotations
from typing import Dict, Optional
from dataclasses import dataclass


SUPPORTED_LANGUAGES = {
    "es": "Español",
    "en": "English", 
    "pt": "Português",
    "fr": "Français",
    "de": "Deutsch",
}

DEFAULT_LANGUAGE = "es"


@dataclass
class TranslationSet:
    ui: Dict[str, str]
    bot: Dict[str, str]
    demo: Dict[str, str]
    admin: Dict[str, str]


def _es() -> TranslationSet:
    return TranslationSet(
        ui={
            "dashboard": "Dashboard",
            "instances": "Instancias",
            "status": "Estado",
            "running": "Ejecutando",
            "stopped": "Detenida",
            "error": "Error",
            "start": "Iniciar",
            "stop": "Detener",
            "restart": "Reiniciar",
            "delete": "Eliminar",
            "create": "Crear",
            "cancel": "Cancelar",
            "confirm": "Confirmar",
            "back": "Volver",
            "next": "Siguiente",
            "help": "Ayuda",
            "loading": "Cargando...",
            "success": "Éxito",
            "warning": "Advertencia",
            "language": "Idioma",
            "select_language": "Seleccionar idioma",
            "enter_number": "Ingresa un número",
            "press_enter": "Presiona Enter",
            "no_instances": "No hay instancias",
            "create_first": "Crea tu primera instancia",
            "exit": "Salir",
            "menu": "Menú",
            "options": "Opciones",
            "install": "Instalar",
            "init": "Iniciar",
            "new": "Nueva",
            "list": "Listar",
            "chat": "Chat",
            "sync": "Sincronizar",
            "fix": "Reparar",
            "health": "Salud",
            "logs": "Logs",
            "config": "Configurar",
            "guide": "Guía",
            "doctor": "Doctor",
            "upgrade": "Actualizar",
            "metrics": "Métricas",
            "stats": "Estadísticas",
            "backup": "Backup",
            "test": "Probar",
            "secure": "Seguridad",
            "welcome": "Bienvenido a Melissa",
            "enter_choice": "Ingresa tu opción",
        },
        bot={
            "welcome": "¡Hola! 👋 Soy Melissa, tu asistente virtual. ¿En qué puedo ayudarte hoy?",
            "greeting": "¡Hola! ¿Cómo estás?",
            "thanks": "¡Gracias por tu confianza!",
            "goodbye": "Fue un placer ayudarte. ¡Hasta pronto! 👋",
            "processing": "Déjame un momento...",
            "typing": "Escribiendo...",
            "error_occurred": "Ups, algo salió mal. Intenta de nuevo.",
            "not_understood": "No entendí tu mensaje. ¿Podrías reformularlo?",
            "menu": "Te muestro las opciones:",
            "hours": "Horario de atención",
            "location": "Ubicación",
            "contact": "Contacto",
            "appointment": "Reservar cita",
            "services": "Servicios",
            "pricing": "Precios",
            "more_help": "¿Necesitas algo más?",
        },
        demo={
            "enter_name": "Ingresa tu nombre",
            "enter_email": "Ingresa tu email",
            "enter_phone": "Ingresa tu teléfono",
            "ask_interest": "¿Qué te interesa?",
            "schedule_demo": "Programar demo",
            "demo_confirmed": "¡Demo confirmada! Te contactaremos pronto.",
            "company_name": "Nombre de empresa",
            "company_size": "Tamaño de empresa",
        },
        admin={
            "welcome_admin": "Panel de Administración",
            "total_instances": "Total de instancias",
            "active_conversations": "Conversaciones activas",
            "total_users": "Total de usuarios",
            "system_health": "Salud del sistema",
            "quick_actions": "Acciones rápidas",
            "recent_activity": "Actividad reciente",
            "settings": "Configuración",
            "users": "Usuarios",
            "billing": "Facturación",
            "reports": "Reportes",
            "security": "Seguridad",
        },
    )


def _en() -> TranslationSet:
    return TranslationSet(
        ui={
            "dashboard": "Dashboard",
            "instances": "Instances",
            "status": "Status",
            "running": "Running",
            "stopped": "Stopped",
            "error": "Error",
            "start": "Start",
            "stop": "Stop",
            "restart": "Restart",
            "delete": "Delete",
            "create": "Create",
            "cancel": "Cancel",
            "confirm": "Confirm",
            "back": "Back",
            "next": "Next",
            "help": "Help",
            "loading": "Loading...",
            "success": "Success",
            "warning": "Warning",
            "language": "Language",
            "select_language": "Select language",
            "enter_number": "Enter a number",
            "press_enter": "Press Enter",
            "no_instances": "No instances",
            "create_first": "Create your first instance",
            "exit": "Exit",
            "menu": "Menu",
            "options": "Options",
            "install": "Install",
            "init": "Initialize",
            "new": "New",
            "list": "List",
            "chat": "Chat",
            "sync": "Sync",
            "fix": "Fix",
            "health": "Health",
            "logs": "Logs",
            "config": "Configure",
            "guide": "Guide",
            "doctor": "Doctor",
            "upgrade": "Upgrade",
            "metrics": "Metrics",
            "stats": "Statistics",
            "backup": "Backup",
            "test": "Test",
            "secure": "Security",
            "welcome": "Welcome to Melissa",
            "enter_choice": "Enter your option",
        },
        bot={
            "welcome": "Hello! 👋 I'm Melissa, your virtual assistant. How can I help you today?",
            "greeting": "Hi! How are you?",
            "thanks": "Thanks for your trust!",
            "goodbye": "It was a pleasure helping you. See you soon! 👋",
            "processing": "Give me a moment...",
            "typing": "Typing...",
            "error_occurred": "Oops, something went wrong. Try again.",
            "not_understood": "I didn't understand your message. Could you rephrase it?",
            "menu": "Here are the options:",
            "hours": "Business hours",
            "location": "Location",
            "contact": "Contact",
            "appointment": "Book appointment",
            "services": "Services",
            "pricing": "Pricing",
            "more_help": "Do you need anything else?",
        },
        demo={
            "enter_name": "Enter your name",
            "enter_email": "Enter your email",
            "enter_phone": "Enter your phone",
            "ask_interest": "What are you interested in?",
            "schedule_demo": "Schedule demo",
            "demo_confirmed": "Demo confirmed! We'll contact you soon.",
            "company_name": "Company name",
            "company_size": "Company size",
        },
        admin={
            "welcome_admin": "Admin Panel",
            "total_instances": "Total instances",
            "active_conversations": "Active conversations",
            "total_users": "Total users",
            "system_health": "System health",
            "quick_actions": "Quick actions",
            "recent_activity": "Recent activity",
            "settings": "Settings",
            "users": "Users",
            "billing": "Billing",
            "reports": "Reports",
            "security": "Security",
        },
    )


def _pt() -> TranslationSet:
    return TranslationSet(
        ui={
            "dashboard": "Painel",
            "instances": "Instâncias",
            "status": "Estado",
            "running": "Executando",
            "stopped": "Parada",
            "error": "Erro",
            "start": "Iniciar",
            "stop": "Parar",
            "restart": "Reiniciar",
            "delete": "Excluir",
            "create": "Criar",
            "cancel": "Cancelar",
            "confirm": "Confirmar",
            "back": "Voltar",
            "next": "Próximo",
            "help": "Ajuda",
            "loading": "Carregando...",
            "success": "Sucesso",
            "warning": "Aviso",
            "language": "Idioma",
            "select_language": "Selecionar idioma",
            "enter_number": "Digite um número",
            "press_enter": "Pressione Enter",
            "no_instances": "Sem instâncias",
            "create_first": "Crie sua primeira instância",
            "exit": "Sair",
            "menu": "Menu",
            "options": "Opções",
            "install": "Instalar",
            "init": "Iniciar",
            "new": "Nova",
            "list": "Listar",
            "chat": "Chat",
            "sync": "Sincronizar",
            "fix": "Corrigir",
            "health": "Saúde",
            "logs": "Logs",
            "config": "Configurar",
            "guide": "Guia",
            "doctor": "Doutor",
            "upgrade": "Atualizar",
            "metrics": "Métricas",
            "stats": "Estatísticas",
            "backup": "Backup",
            "test": "Testar",
            "secure": "Segurança",
            "welcome": "Bem-vindo ao Melissa",
            "enter_choice": "Digite sua opção",
        },
        bot={
            "welcome": "Olá! 👋 Sou a Melissa, sua assistente virtual. Como posso ajudar hoje?",
            "greeting": "Oi! Como você está?",
            "thanks": "Obrigado pela sua confiança!",
            "goodbye": "Foi um prazer ajudar. Até logo! 👋",
            "processing": "Me dê um momento...",
            "typing": "Digitando...",
            "error_occurred": "Ops, algo deu errado. Tente novamente.",
            "not_understood": "Não entendi sua mensagem. Poderia reformular?",
            "menu": "Aqui estão as opções:",
            "hours": "Horário de funcionamento",
            "location": "Localização",
            "contact": "Contato",
            "appointment": "Agendar consulta",
            "services": "Serviços",
            "pricing": "Preços",
            "more_help": "Precisa de mais alguma coisa?",
        },
        demo={
            "enter_name": "Digite seu nome",
            "enter_email": "Digite seu email",
            "enter_phone": "Digite seu telefone",
            "ask_interest": "No que você tem interesse?",
            "schedule_demo": "Agendar demo",
            "demo_confirmed": "Demo confirmada! Entraremos em contato em breve.",
            "company_name": "Nome da empresa",
            "company_size": "Tamanho da empresa",
        },
        admin={
            "welcome_admin": "Painel de Administração",
            "total_instances": "Total de instâncias",
            "active_conversations": "Conversas ativas",
            "total_users": "Total de usuários",
            "system_health": "Saúde do sistema",
            "quick_actions": "Ações rápidas",
            "recent_activity": "Atividade recente",
            "settings": "Configurações",
            "users": "Usuários",
            "billing": "Faturamento",
            "reports": "Relatórios",
            "security": "Segurança",
        },
    )


def _fr() -> TranslationSet:
    return TranslationSet(
        ui={
            "dashboard": "Tableau de bord",
            "instances": "Instances",
            "status": "Statut",
            "running": "En cours",
            "stopped": "Arrêté",
            "error": "Erreur",
            "start": "Démarrer",
            "stop": "Arrêter",
            "restart": "Redémarrer",
            "delete": "Supprimer",
            "create": "Créer",
            "cancel": "Annuler",
            "confirm": "Confirmer",
            "back": "Retour",
            "next": "Suivant",
            "help": "Aide",
            "loading": "Chargement...",
            "success": "Succès",
            "warning": "Avertissement",
            "language": "Langue",
            "select_language": "Sélectionner la langue",
            "enter_number": "Entrez un numéro",
            "press_enter": "Appuyez sur Entrée",
            "no_instances": "Aucune instance",
            "create_first": "Créez votre première instance",
            "exit": "Quitter",
            "menu": "Menu",
            "options": "Options",
            "install": "Installer",
            "init": "Initialiser",
            "new": "Nouveau",
            "list": "Lister",
            "chat": "Chat",
            "sync": "Synchroniser",
            "fix": "Corriger",
            "health": "Santé",
            "logs": "Journaux",
            "config": "Configurer",
            "guide": "Guide",
            "doctor": "Docteur",
            "upgrade": "Mettre à jour",
            "metrics": "Métriques",
            "stats": "Statistiques",
            "backup": "Sauvegarde",
            "test": "Tester",
            "secure": "Sécurité",
            "welcome": "Bienvenue sur Melissa",
            "enter_choice": "Entrez votre option",
        },
        bot={
            "welcome": "Bonjour! 👋 Je suis Melissa, votre assistante virtuelle. Comment puis-je vous aider aujourd'hui?",
            "greeting": "Salut! Comment allez-vous?",
            "thanks": "Merci pour votre confiance!",
            "goodbye": "Ce fut un plaisir de vous aider. À bientôt! 👋",
            "processing": "Donnez-moi un moment...",
            "typing": "En train d'écrire...",
            "error_occurred": "Oups, quelque chose s'est mal passé. Réessayez.",
            "not_understood": "Je n'ai pas compris votre message. Pourriez-vous le reformuler?",
            "menu": "Voici les options:",
            "hours": "Heures d'ouverture",
            "location": "Emplacement",
            "contact": "Contact",
            "appointment": "Prendre rendez-vous",
            "services": "Services",
            "pricing": "Tarifs",
            "more_help": "Avez-vous besoin d'autre chose?",
        },
        demo={
            "enter_name": "Entrez votre nom",
            "enter_email": "Entrez votre email",
            "enter_phone": "Entrez votre téléphone",
            "ask_interest": "Qu'est-ce qui vous intéresse?",
            "schedule_demo": "Planifier une démo",
            "demo_confirmed": "Démo confirmée! Nous vous contacterons bientôt.",
            "company_name": "Nom de l'entreprise",
            "company_size": "Taille de l'entreprise",
        },
        admin={
            "welcome_admin": "Panneau d'administration",
            "total_instances": "Total des instances",
            "active_conversations": "Conversations actives",
            "total_users": "Total des utilisateurs",
            "system_health": "Santé du système",
            "quick_actions": "Actions rapides",
            "recent_activity": "Activité récente",
            "settings": "Paramètres",
            "users": "Utilisateurs",
            "billing": "Facturation",
            "reports": "Rapports",
            "security": "Sécurité",
        },
    )


def _de() -> TranslationSet:
    return TranslationSet(
        ui={
            "dashboard": "Dashboard",
            "instances": "Instanzen",
            "status": "Status",
            "running": "Läuft",
            "stopped": "Gestoppt",
            "error": "Fehler",
            "start": "Starten",
            "stop": "Stoppen",
            "restart": "Neustarten",
            "delete": "Löschen",
            "create": "Erstellen",
            "cancel": "Abbrechen",
            "confirm": "Bestätigen",
            "back": "Zurück",
            "next": "Weiter",
            "help": "Hilfe",
            "loading": "Laden...",
            "success": "Erfolg",
            "warning": "Warnung",
            "language": "Sprache",
            "select_language": "Sprache auswählen",
            "enter_number": "Nummer eingeben",
            "press_enter": "Enter drücken",
            "no_instances": "Keine Instanzen",
            "create_first": "Erstellen Sie Ihre erste Instanz",
            "exit": "Beenden",
            "menu": "Menü",
            "options": "Optionen",
            "install": "Installieren",
            "init": "Initialisieren",
            "new": "Neu",
            "list": "Auflisten",
            "chat": "Chat",
            "sync": "Synchronisieren",
            "fix": "Beheben",
            "health": "Gesundheit",
            "logs": "Protokolle",
            "config": "Konfigurieren",
            "guide": "Anleitung",
            "doctor": "Doktor",
            "upgrade": "Aktualisieren",
            "metrics": "Metriken",
            "stats": "Statistiken",
            "backup": "Sicherung",
            "test": "Testen",
            "secure": "Sicherheit",
            "welcome": "Willkommen bei Melissa",
            "enter_choice": "Option eingeben",
        },
        bot={
            "welcome": "Hallo! 👋 Ich bin Melissa, Ihre virtuelle Assistentin. Wie kann ich Ihnen heute helfen?",
            "greeting": "Hi! Wie geht es Ihnen?",
            "thanks": "Vielen Dank für Ihr Vertrauen!",
            "goodbye": "Es war mir eine Freude zu helfen. Bis bald! 👋",
            "processing": "Gib mir einen Moment...",
            "typing": "Schreiben...",
            "error_occurred": "Hoppla, etwas ist schief gelaufen. Versuchen Sie es erneut.",
            "not_understood": "Ich habe Ihre Nachricht nicht verstanden. Könnten Sie sie umformulieren?",
            "menu": "Hier sind die Optionen:",
            "hours": "Öffnungszeiten",
            "location": "Standort",
            "contact": "Kontakt",
            "appointment": "Termin buchen",
            "services": "Dienstleistungen",
            "pricing": "Preise",
            "more_help": "Brauchen Sie noch etwas?",
        },
        demo={
            "enter_name": "Geben Sie Ihren Namen ein",
            "enter_email": "Geben Sie Ihre E-Mail ein",
            "enter_phone": "Geben Sie Ihre Telefonnummer ein",
            "ask_interest": "Was interessiert Sie?",
            "schedule_demo": "Demo planen",
            "demo_confirmed": "Demo bestätigt! Wir werden Sie bald kontaktieren.",
            "company_name": "Firmenname",
            "company_size": "Unternehmensgröße",
        },
        admin={
            "welcome_admin": "Admin-Panel",
            "total_instances": "Gesamte Instanzen",
            "active_conversations": "Aktive Gespräche",
            "total_users": "Gesamte Benutzer",
            "system_health": "Systemzustand",
            "quick_actions": "Schnellaktionen",
            "recent_activity": "Letzte Aktivität",
            "settings": "Einstellungen",
            "users": "Benutzer",
            "billing": "Abrechnung",
            "reports": "Berichte",
            "security": "Sicherheit",
        },
    )


_TRANSLATIONS: Dict[str, TranslationSet] = {
    "es": _es(),
    "en": _en(),
    "pt": _pt(),
    "fr": _fr(),
    "de": _de(),
}


class I18n:
    def __init__(self, lang: str = DEFAULT_LANGUAGE):
        self.lang = lang if lang in _TRANSLATIONS else DEFAULT_LANGUAGE
        self._cache: Dict[str, str] = {}

    def t(self, key: str, category: str = "ui") -> str:
        cache_key = f"{self.lang}:{category}:{key}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        translations = _TRANSLATIONS.get(self.lang)
        if translations is None:
            translations = _TRANSLATIONS[DEFAULT_LANGUAGE]
        
        category_dict = getattr(translations, category, {})
        result = category_dict.get(key, key)
        self._cache[cache_key] = result
        return result

    def ui(self, key: str) -> str:
        return self.t(key, "ui")

    def bot(self, key: str) -> str:
        return self.t(key, "bot")

    def demo(self, key: str) -> str:
        return self.t(key, "demo")

    def admin(self, key: str) -> str:
        return self.t(key, "admin")

    def set_lang(self, lang: str) -> None:
        if lang in _TRANSLATIONS:
            self.lang = lang
            self._cache.clear()

    @property
    def current_lang(self) -> str:
        return self.lang

    @property
    def available_languages(self) -> Dict[str, str]:
        return SUPPORTED_LANGUAGES.copy()


_global_i18n: I18n = I18n()


def get_i18n() -> I18n:
    return _global_i18n


def set_language(lang: str) -> None:
    _global_i18n.set_lang(lang)


def t(key: str, category: str = "ui") -> str:
    return _global_i18n.t(key, category)


def detect_user_language(text: str) -> str:
    text_lower = text.lower()
    
    spanish_indicators = ["hola", "gracias", "buenos", "cómo", "quiero", "necesito", "hablar", "dónde", "cuándo", "cuánto"]
    english_indicators = ["hello", "thanks", "hi", "how", "want", "need", "speak", "where", "when", "how much"]
    portuguese_indicators = ["oi", "obrigado", "ola", "como", "quero", "preciso", "falar", "onde", "quando", "quanto"]
    french_indicators = ["bonjour", "merci", "salut", "comment", "vouloir", "besoin", "parler", "où", "quand", "combien"]
    german_indicators = ["hallo", "danke", "hi", "wie", "wollen", "brauchen", "sprechen", "wo", "wann", "wie viel"]

    for word in spanish_indicators:
        if word in text_lower:
            return "es"
    for word in english_indicators:
        if word in text_lower:
            return "en"
    for word in portuguese_indicators:
        if word in text_lower:
            return "pt"
    for word in french_indicators:
        if word in text_lower:
            return "fr"
    for word in german_indicators:
        if word in text_lower:
            return "de"
    
    return DEFAULT_LANGUAGE


LANGUAGE_MENU = {
    "es": "🇪🇸 Español",
    "en": "🇬🇧 English",
    "pt": "🇧🇷 Português",
    "fr": "🇫🇷 Français",
    "de": "🇩🇪 Deutsch",
}