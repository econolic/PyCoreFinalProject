add-import json
import logging
import re
from datetime import datetime, date
from typing import List, Optional, Dict, Type, TypeVar, Generic, Any, Tuple
from collections import UserDict, deque
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from colorama import Fore, Style, init
from difflib import get_close_matches
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter

# Ініціалізація colorama
init(autoreset=True)

# ------------------------------------------------------
# Константи та глобальні налаштування
# ------------------------------------------------------
MAX_UNDO_STEPS = 10
CONTACTS_FILE = "contacts.json"
NOTES_FILE = "notes.json"

logging.basicConfig(
    filename="personal_assistant.log",
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s: %(message)s"
)

# Константи
MAX_UNDO_STEPS = 10
CONTACTS_FILE = "contacts.json"
NOTES_FILE = "notes.json"

# ------------------------------------------------------
# Утиліти для форматованого виводу
# ------------------------------------------------------

def print_border(title: str = "", width: int = 60) -> None:
    """Друкує верхню рамку з опціональним заголовком."""
    if title:
        text_len = len(title) + 2
        if text_len > width - 4:
            text_len = width - 4
        left_part = "─" * 2
        mid_part = f" {title} "
        right_len = width - 2 - len(mid_part)
        if right_len < 0:
            right_len = 0
        right_part = "─" * right_len
        print(Fore.YELLOW + left_part + mid_part + right_part + Style.RESET_ALL)
    else:
        print(Fore.YELLOW + "─" * width + Style.RESET_ALL)

def print_bottom_border(width: int = 60) -> None:
    """Друкує нижню горизонтальну межу."""
    print(Fore.YELLOW + "─" * width + Style.RESET_ALL)

def print_colored_box(header: str, lines: List[str], width: int = 60) -> None:
    """Друкує текст у кольоровій рамці з заголовком."""
    print_border(header, width)
    for line in lines:
        print(line)
    print_bottom_border(width)

def indent_lines(lines: List[str], spaces: int = 2) -> str:
    """Додає відступ до кожного рядка."""
    prefix = " " * spaces
    return "\n".join(prefix + line for line in lines)

def format_contact(contact: "Contact") -> str:
    """Форматує відображення контакту у багаторядковий блок."""
    lines = []
    lines.append(f"{Fore.CYAN}Name:{Style.RESET_ALL} {contact.name}")
    if contact.phones:
        lines.append(f"{Fore.CYAN}Phones:{Style.RESET_ALL}")
        for phone in contact.phones:
            lines.append(f"  {phone}")
    else:
        lines.append(f"{Fore.CYAN}Phones:{Style.RESET_ALL} (немає)")

    if contact.emails:
        lines.append(f"{Fore.CYAN}Emails:{Style.RESET_ALL}")
        for email in contact.emails:
            lines.append(f"  {email}")
    else:
        lines.append(f"{Fore.CYAN}Emails:{Style.RESET_ALL} (немає)")

    if contact.birthday:
        bday_str = contact.birthday.strftime("%d.%m.%Y")
        lines.append(f"{Fore.CYAN}Birthday:{Style.RESET_ALL} {bday_str}")
        days = contact.days_to_birthday()
        age_val = contact.age()
        lines.append(f"  Days to next BDay: {days if days is not None else '-'}")
        lines.append(f"  Age: {age_val if age_val is not None else '-'}")
    else:
        lines.append(f"{Fore.CYAN}Birthday:{Style.RESET_ALL} (не вказано)")

    return "\n".join(lines)

def format_note(note: "Note") -> str:
    """Форматує відображення нотатки у багаторядковий блок."""
    lines = []
    lines.append(f"{Fore.MAGENTA}Text:{Style.RESET_ALL} {note.text}")
    if note.tags:
        lines.append(f"{Fore.MAGENTA}Tags:{Style.RESET_ALL} " + ", ".join(note.tags))
    else:
        lines.append(f"{Fore.MAGENTA}Tags:{Style.RESET_ALL} (немає)")
    created_str = note.created_at.strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"Created at: {created_str}")
    return "\n".join(lines)

def format_help_table(commands_data: List[List[str]], title: str = "Commands", width: int = 72) -> str:
    """Форматує допоміжну таблицю з командами."""
    max_cmd_len = max(len(row[0]) for row in commands_data)
    output_lines = []
    separator = "+" + "-"*(width-2) + "+"
    header_line = f"| {title.center(width-2)} |"
    output_lines.append(separator)
    output_lines.append(header_line)
    output_lines.append(separator)
    for cmd, desc in commands_data:
        line = f"| {Fore.CYAN}{cmd:<{max_cmd_len}}{Style.RESET_ALL} : {desc}"
        space_left = width - 2 - len(line)
        if space_left < 0:
            space_left = 0
        line += " " * space_left + "|"
        output_lines.append(line)
    output_lines.append(separator)
    return "\n".join(output_lines)

# ------------------------------------------------------
# Базові класи даних
# ------------------------------------------------------

class BaseEntry(ABC):
    """Абстрактний базовий клас для записів."""
    id: int

    @abstractmethod
    def to_dict(self) -> dict:
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> "BaseEntry":
        pass

    @abstractmethod
    def matches(self, query: str) -> bool:
        pass

    @abstractmethod
    def update(self, **fields):
        pass

@dataclass
class Contact(BaseEntry):
    id: int
    name: str
    phones: List[str] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)
    birthday: Optional[date] = None

    def __post_init__(self):
        if self.birthday and isinstance(self.birthday, str):
            fmt_candidates = ["%d.%m.%Y", "%Y-%m-%d"]
            parsed = None
            for fmt in fmt_candidates:
                try:
                    parsed = datetime.strptime(self.birthday, fmt).date()
                    break
                except ValueError:
                    continue
            if not parsed:
                raise ValueError("Дата народження в неправильному форматі.")
            self.birthday = parsed

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "phones": self.phones,
            "emails": self.emails,
            "birthday": self.birthday.strftime("%Y-%m-%d") if self.birthday else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Contact":
        return cls(
            id=data["id"],
            name=data["name"],
            phones=data.get("phones", []),
            emails=data.get("emails", []),
            birthday=data.get("birthday")
        )

    def matches(self, query: str) -> bool:
        q = query.lower()
        if q in self.name.lower():
            return True
        for p in self.phones:
            if q in p:
                return True
        for e in self.emails:
            if q in e.lower():
                return True
        if self.birthday and q in self.birthday.strftime("%d.%m.%Y"):
            return True
        return False

    def update(self, **fields):
        if "name" in fields:
            self.name = fields["name"]
        if "phones" in fields:
            self.phones = fields["phones"]
        if "emails" in fields:
            self.emails = fields["emails"]
        if "birthday" in fields:
            self.birthday = fields["birthday"]
            if isinstance(self.birthday, str):
                fmt_candidates = ["%d.%m.%Y", "%Y-%m-%d"]
                parsed = None
                for fmt in fmt_candidates:
                    try:
                        parsed = datetime.strptime(self.birthday, fmt).date()
                        break
                    except ValueError:
                        continue
                if not parsed:
                    raise ValueError("Дата народження в неправильному форматі.")
                self.birthday = parsed

    def birthday_str(self) -> str:
        return self.birthday.strftime("%d.%m.%Y") if self.birthday else ""

    def days_to_birthday(self) -> Optional[int]:
        if not self.birthday:
            return None
        today = date.today()
        bday = self.birthday.replace(year=today.year)
        if bday < today:
            bday = bday.replace(year=today.year + 1)
        return (bday - today).days

    def age(self) -> Optional[int]:
        if not self.birthday:
            return None
        today = date.today()
        return today.year - self.birthday.year - ((today.month, today.day) < (self.birthday.month, self.birthday.day))

@dataclass
class Note(BaseEntry):
    id: int
    text: str
    tags: List[str] = field(default_factory=list)
    contact_ids: List[int] = field(default_factory=list)  # ДОДАНЕ ПОЛЕ для зв’язку
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.text.strip():
            raise ValueError("Текст нотатки не може бути порожнім.")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "tags": self.tags,
            "contact_ids": self.contact_ids,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Note":
        created_str = data.get("created_at")
        created_dt = datetime.now()
        if created_str:
            try:
                created_dt = datetime.strptime(created_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        return cls(
            id=data["id"],
            text=data["text"],
            tags=data.get("tags", []),
            contact_ids=data.get("contact_ids", []),
            created_at=created_dt
        )

    def matches(self, query: str) -> bool:
        q = query.lower()
        if q in self.text.lower():
            return True
        for tag in self.tags:
            if q in tag.lower():
                return True
        return False

    def update(self, **fields):
        if "text" in fields:
            self.text = fields["text"]
        if "tags" in fields:
            self.tags = fields["tags"]
        if "contact_ids" in fields:
            self.contact_ids = fields["contact_ids"]

# ------------------------------------------------------
# Універсальні колекції
# ------------------------------------------------------

E = TypeVar("E", bound=BaseEntry)

class BaseBook(UserDict, Generic[E]):
    entry_class: Type[E] = BaseEntry
    entry_type_name: str = "entry"

    def __init__(self):
        super().__init__()
        self.undo_stack = deque(maxlen=MAX_UNDO_STEPS)
        self._max_id = 0

    def add(self, entry: E) -> int:
        if entry.id == 0:
            entry.id = self._max_id + 1
        self._max_id = max(self._max_id, entry.id)
        self.undo_stack.append(("add", entry.id, None))
        self.data[entry.id] = entry
        return entry.id

    def create_and_add(self, **kwargs) -> int:
        entry = self.entry_class(id=0, **kwargs)
        return self.add(entry)

    def find_by_id(self, id_val: int) -> E:
        if id_val not in self.data:
            raise KeyError(f"{self.entry_type_name} з ID={id_val} не знайдено.")
        return self.data[id_val]

    def find(self, query: str) -> List[E]:
        return [entry for entry in self.data.values() if entry.matches(query)]

    def edit(self, id_val: int, **changes) -> None:
        old_entry = self.find_by_id(id_val)
        old_copy = self.entry_class.from_dict(old_entry.to_dict())
        self.undo_stack.append(("edit", id_val, old_copy))
        old_entry.update(**changes)

    def delete(self, id_val: int) -> bool:
        if id_val in self.data:
            old_entry = self.data[id_val]
            self.undo_stack.append(("delete", id_val, old_entry))
            del self.data[id_val]
            return True
        return False

    def undo(self) -> str:
        if not self.undo_stack:
            return "Немає дій для скасування."
        action, id_val, old_value = self.undo_stack.pop()
        if action == "add":
            if id_val in self.data:
                del self.data[id_val]
            return f"Скасовано додавання {self.entry_type_name} з ID {id_val}."
        elif action == "delete":
            self.data[id_val] = old_value
            return f"Відновлено {self.entry_type_name} з ID {id_val}."
        elif action == "edit":
            self.data[id_val] = old_value
            return f"Скасовано редагування {self.entry_type_name} з ID {id_val}."
        return "Невідома операція для undo."

    def save(self, filename: str) -> None:
        save_dict = {str(eid): entry.to_dict() for eid, entry in self.data.items()}
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(save_dict, f, ensure_ascii=False, indent=4)

    @classmethod
    def load(cls, filename: str) -> "BaseBook":
        new_book = cls()
        try:
            with open(filename, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print(Fore.YELLOW + f"Файл {filename} не знайдено або пошкоджено. Створено порожню книгу." + Style.RESET_ALL)
            return new_book
        for k, v in raw.items():
            eid = int(k)
            entry = cls.entry_class.from_dict(v)
            new_book.data[eid] = entry
            new_book._max_id = max(new_book._max_id, eid)
        return new_book

class AddressBook(BaseBook[Contact]):
    entry_class = Contact
    entry_type_name = "контакт"

    def get_upcoming_birthdays(self, days_ahead: int = 7) -> List[Contact]:
        today = date.today()
        results = []
        for c in self.data.values():
            if not c.birthday:
                continue
            bday_this_year = c.birthday.replace(year=today.year)
            if bday_this_year < today:
                bday_this_year = bday_this_year.replace(year=today.year + 1)
            if 0 <= (bday_this_year - today).days < days_ahead:
                results.append(c)
        return results

    def create_note_for_contact(
        self,
        nbook: "Notebook",
        contact_id: int,
        text: str,
        tags: Optional[List[str]] = None
    ) -> int:
        """
        Створює нотатку в Notebook з прив'язкою до заданого контакту.
        Повертає ID створеної нотатки.
        """
        if contact_id not in self.data:
            raise KeyError(f"Контакт з ID={contact_id} не знайдено.")

        return nbook.create_and_add(
            text=text,
            tags=tags if tags else [],
            contact_ids=[contact_id]
        )

class Notebook(BaseBook[Note]):
    entry_class = Note
    entry_type_name = "нотатку"

    def sort_by_date(self) -> List[Note]:
        return sorted(self.data.values(), key=lambda x: x.created_at)

    def find_by_tag(self, tag: str) -> List[Note]:
        tag_lower = tag.lower()
        return [note for note in self.data.values() if any(tag_lower in t.lower() for t in note.tags)]

    def find_by_date(self, date_str: str) -> List[Note]:
        try:
            target = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Дата повинна бути у форматі YYYY-MM-DD")
        return [n for n in self.data.values() if n.created_at.date() == target]

    def find_by_contact_id(self, contact_id: int) -> List[Note]:
        """Повертає список нотаток, прив'язаних до контакту з даним ID."""
        return [note for note in self.data.values() if contact_id in note.contact_ids]

# ------------------------------------------------------
# Декоратор для обробки помилок
# ------------------------------------------------------
def input_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyError as e:
            logging.error(f"KeyError in {func.__name__}: {e}")
            print(Fore.RED + str(e) + Style.RESET_ALL)
        except ValueError as e:
            logging.error(f"ValueError in {func.__name__}: {e}")
            print(Fore.RED + str(e) + Style.RESET_ALL)
        except IndexError:
            logging.error(f"IndexError in {func.__name__}: Недостатньо аргументів.")
            print(Fore.RED + "Неправильний формат команди або недостатньо аргументів." + Style.RESET_ALL)
        except Exception as e:
            logging.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            print(Fore.RED + f"Сталася несподівана помилка: {e}" + Style.RESET_ALL)
    return wrapper

# ------------------------------------------------------
# Функції-утиліти CLI
# ------------------------------------------------------
def parse_contact_input(tokens: List[str]) -> Dict[str, Any]:
    """
    Якщо дані передано у вигляді одного рядка,
    розділяємо токени: всі токени, що не є телефоном або email, формують ім'я.
    """
    phone = None
    emails = []
    name_parts = []
    for token in tokens:
        if token.isdigit() and len(token) == 10 and phone is None:
            phone = token
        elif "@" in token:
            emails.append(token)
        else:
            name_parts.append(token)
    name = " ".join(name_parts).strip()
    result = {"name": name}
    if phone:
        result["phones"] = [phone]
    if emails:
        result["emails"] = emails
    return result

@input_error
def add_contact(args: List[str], abook: AddressBook, nbook: Notebook):
    """
    add-contact [дані в один рядок] або інтерактивно.
    Приклад рядком: add-contact John Galt 1234567890 john@example.com
    Після створення пропонує створити нотатку для щойно доданого контакту.
    """
    if args:
        data = parse_contact_input(args)
        if "name" in data:
            data["name"] = normalize_name(data["name"])  # нормалізація ім'я
        if "phones" in data:
            valid_phones = []
            for p in data["phones"]:
                norm_phone = validate_phone(p)
                if norm_phone:
                    valid_phones.append(norm_phone)
                else:
                    raise ValueError("Телефон має бути у форматі +380XXXXXXXXX або 0XXXXXXXXX")
            data["phones"] = valid_phones

    else:
        while True:
            name = input("Enter full name: ").strip()
            if name:
                name = normalize_name(name)
                break
            print(Fore.RED + "Ім'я не може бути порожнім." + Style.RESET_ALL)
        
        phones = []
        while True:    
            phone = input("Enter phone (optional, format +380XXXXXXXXX or 0XXXXXXXXX): ").strip()
            if not phone:
                break
            norm = validate_phone(phone)
            if norm:
                phones = [norm if isinstance(norm, str) else str(norm)]
                break
            print(Fore.RED + "Телефон має бути у форматі +380XXXXXXXXX або 0XXXXXXXXX." + Style.RESET_ALL)
        
        emails = []
        while True:
            emails_str = input("Enter emails (optional, separated by space): ").strip()
            if not emails_str:
                break
            emails = emails_str.split()
            if all(validate_email(e) for e in emails):
                break
            print(Fore.RED + "Один або кілька email некоректні. Спробуйте ще раз." + Style.RESET_ALL)
        
        birthday = None
        while True:
            birthday_input = input("Enter birthday (optional, DD.MM.YYYY or YYYY-MM-DD): ").strip()
            if not birthday_input:
                break
            if validate_birthday(birthday_input):
                birthday = birthday_input
                break
            print(Fore.RED + "Неправильний формат дати. Спробуйте ще раз." + Style.RESET_ALL)
        data = {"name": name}
        if phone:
            data["phones"] = phones
        if emails_str:
            data["emails"] = emails_str.split()
        if birthday:
            data["birthday"] = birthday

    new_id = abook.create_and_add(**data)
    contact_obj = abook.find_by_id(new_id)
    block = format_contact(contact_obj)
    print_colored_box(f"Contact added (ID={new_id})", block.split("\n"))

    # -------------------------------
    # Пропонуємо одразу створити нотатку
    choice = input("Create a note for this contact? [Y/n]: ").strip().lower()
    if choice in ("", "y", "yes"):
        note_text = input("Enter note text: ").strip()
        if not note_text:
            print(Fore.YELLOW + "No note text entered, skip note creation." + Style.RESET_ALL)
            return
        tags_input = input("Enter #tags (optional, separated by space): ").strip()
        tags = [t.lstrip('#') for t in tags_input.split()] if tags_input else []

        note_id = abook.create_note_for_contact(
            nbook=nbook,
            contact_id=new_id,
            text=note_text,
            tags=tags
        )
        note_obj = nbook.find_by_id(note_id)
        note_block = format_note(note_obj)
        # Для наочності додамо ім'я контакту в блок:
        note_lines = note_block.split("\n")
        note_lines.insert(1, f"{Fore.MAGENTA}Linked contact:{Style.RESET_ALL} {contact_obj.name}")
        note_block = "\n".join(note_lines)
        print_colored_box(
            f"New note for contact (ID={new_id}, note ID={note_id})",
            note_block.split("\n")
        )
    else:
        print("Skip note creation.")

@input_error
def list_contacts(args: List[str], abook: AddressBook):
    if not abook.data:
        print(Fore.YELLOW + "У книзі немає контактів." + Style.RESET_ALL)
        return
    print(Fore.GREEN + f"Усього контактів: {len(abook.data)}" + Style.RESET_ALL)
    for c in abook.data.values():
        block = format_contact(c)
        print_colored_box(f"Contact ID={c.id}", block.split("\n"))

@input_error
def search_contact(args: List[str], abook: AddressBook):
    if not args:
        raise ValueError("Використання: search-contact <query>")
    query = " ".join(args)
    results = abook.find(query)
    if not results:
        print(Fore.CYAN + "Нічого не знайдено." + Style.RESET_ALL)
        return
    print(Fore.GREEN + f"Знайдено {len(results)} результат(ів) за '{query}':" + Style.RESET_ALL)
    for c in results:
        block = format_contact(c)
        print_colored_box(f"Contact ID={c.id}", block.split("\n"))

@input_error
def edit_contact(args: List[str], abook: AddressBook):
    if len(args) < 2:
        raise ValueError("Використання: edit-contact <id> поле=значення ...")
    id_val = int(args[0])
    changes = {}
    for chunk in args[1:]:
        if "=" in chunk:
            key, val = chunk.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key in ("phones", "emails"):
                changes[key] = [x.strip() for x in val.split(",")]
            else:
                changes[key] = val
    abook.edit(id_val, **changes)
    print(Fore.GREEN + f"Контакт ID={id_val} відредаговано." + Style.RESET_ALL)

@input_error
def delete_contact(args: List[str], abook: AddressBook, nbook: "Notebook"):
    if not args:
        raise ValueError("Використання: delete-contact <id>")
    id_val = int(args[0])
    try:
        contact = abook.find_by_id(id_val)
    except KeyError:
        print(Fore.RED + f"Контакт ID={id_val} не знайдено." + Style.RESET_ALL)
        return

    linked_notes = nbook.find_by_contact_id(id_val)
    if linked_notes:
        note_ids = [note.id for note in linked_notes]
        print(Fore.YELLOW + f"Увага: Контакт '{contact.name}' пов'язаний з нотатками {note_ids}." + Style.RESET_ALL)
        choice = input("Видалити пов'язані нотатки (D) чи залишити їх без цього контакту (K)? [D/K]: ").strip().lower()
        if choice == 'd':
            # Видаляємо всі пов'язані нотатки
            for note in linked_notes:
                nbook.delete(note.id)
            print(Fore.MAGENTA + f"Видалено {len(linked_notes)} нотаток, пов'язаних з контактом ID={id_val}." + Style.RESET_ALL)
        else:
            # За замовчуванням - від'єднати контакт (видалити його ID зі списку contact_ids)
            for note in linked_notes:
                if id_val in note.contact_ids:
                    note.contact_ids.remove(id_val)
            print(Fore.MAGENTA + f"Контакт видалено з {len(linked_notes)} нотаток (нотатки збережено)." + Style.RESET_ALL)

    if abook.delete(id_val):
        print(Fore.GREEN + f"Контакт ID={id_val} видалено." + Style.RESET_ALL)
    else:
        print(Fore.RED + f"Контакт ID={id_val} не знайдено." + Style.RESET_ALL)

@input_error
def upcoming_birthdays(args: List[str], abook: AddressBook):
    days = 7
    if args and args[0].startswith("days="):
        try:
            days = int(args[0].split("=", 1)[1])
        except ValueError:
            pass
    results = abook.get_upcoming_birthdays(days_ahead=days)
    if not results:
        print(Fore.CYAN + f"Немає ДН протягом {days} днів." + Style.RESET_ALL)
        return
    print(Fore.GREEN + f"Найближчі ДН протягом {days} днів:" + Style.RESET_ALL)
    for c in results:
        block = format_contact(c)
        print_colored_box(f"Contact ID={c.id}", block.split("\n"))

@input_error
def undo_contact(args: List[str], abook: AddressBook):
    msg = abook.undo()
    print(msg)

# ------------------------------------------------------
# Команди для роботи з нотатками
# ------------------------------------------------------
@input_error
def add_note(args: List[str], nb: Notebook):
    """
    add-note [дані в один рядок] або інтерактивно.
    Приклад рядком: add-note Привіт, світ! #tag1 #tag2
    """
    if args:
        text_parts = [arg for arg in args if not arg.startswith('#')]
        tags = [arg.lstrip('#') for arg in args if arg.startswith('#')]
        text = " ".join(text_parts).strip()
        if not text:
            raise ValueError("Текст нотатки не може бути порожнім.")
        data = {"text": text, "tags": tags, "contact_ids": []}
    else:
        text = input("Enter text: ").strip()
        tags_input = input("Enter #tag (optional): ").strip()
        tags = [t.lstrip('#') for t in tags_input.split()] if tags_input else []
        data = {"text": text, "tags": tags, "contact_ids": []}

    new_id = nb.create_and_add(**data)
    note_obj = nb.find_by_id(new_id)
    block = format_note(note_obj)
    print_colored_box(f"Note added (ID={new_id})", block.split("\n"))

@input_error
def list_notes(args: List[str], nb: Notebook, abook: AddressBook = None):
    if not nb.data:
        print(Fore.YELLOW + "Нотаток ще немає." + Style.RESET_ALL)
        return
    print(Fore.GREEN + f"Усього нотаток: {len(nb.data)}" + Style.RESET_ALL)

    for note in nb.data.values():
        block = format_note(note)
        # Якщо є abook і є contact_ids, покажемо імена контактів
        if abook and note.contact_ids:
            contact_names = []
            for cid in note.contact_ids:
                try:
                    c = abook.find_by_id(cid)
                    contact_names.append(c.name)
                except KeyError:
                    pass
            if contact_names:
                lines = block.split("\n")
                lines.insert(1, f"{Fore.MAGENTA}Contacts:{Style.RESET_ALL} " + ", ".join(contact_names))
                block = "\n".join(lines)
        print_colored_box(f"Note ID={note.id}", block.split("\n"))

@input_error
def search_note(args: List[str], nb: Notebook, abook: AddressBook = None):
    if not args:
        raise ValueError("Використання: search-note <query>")
    query = " ".join(args).lower()
    results = []

    # 1. Пошук за текстом і тегами
    text_matches = nb.find(query)
    results.extend(text_matches)

    # 2. Якщо маємо адресну книгу, шукаємо контакти, де ім'я/телефон/емейл містить query
    if abook:
        contact_matches = abook.find(query)
        for contact in contact_matches:
            # додаємо нотатки, що прив'язані до цього контакту
            for note in nb.find_by_contact_id(contact.id):
                results.append(note)

    # Усуваємо дублікати
    unique_results = {}
    for note in results:
        unique_results[note.id] = note
    results = list(unique_results.values())

    if not results:
        print(Fore.CYAN + "Нічого не знайдено." + Style.RESET_ALL)
        return

    print(Fore.GREEN + f"Знайдено {len(results)} нотаток за запитом '{query}':" + Style.RESET_ALL)
    for n in results:
        block = format_note(n)
        if abook and n.contact_ids:
            contact_names = []
            for cid in n.contact_ids:
                try:
                    c = abook.find_by_id(cid)
                    contact_names.append(c.name)
                except KeyError:
                    pass
            if contact_names:
                lines = block.split("\n")
                lines.insert(1, f"{Fore.MAGENTA}Contacts:{Style.RESET_ALL} " + ", ".join(contact_names))
                block = "\n".join(lines)
        print_colored_box(f"Note ID={n.id}", block.split("\n"))

@input_error
def edit_note(args: List[str], nb: Notebook):
    if len(args) < 2:
        raise ValueError("Використання: edit-note <id> поле=значення ...")
    id_val = int(args[0])
    changes = {}
    for chunk in args[1:]:
        if "=" in chunk:
            key, val = chunk.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key == "tags":
                changes[key] = [x.strip().lstrip('#') for x in val.split(",")]
            elif key == "contact_ids":
                # contact_ids=1,2
                changes[key] = [int(x) for x in re.split(r"[,;\s]+", val) if x.isdigit()]
            else:
                changes[key] = val
    nb.edit(id_val, **changes)
    print(Fore.GREEN + f"Нотатку ID={id_val} відредаговано." + Style.RESET_ALL)

@input_error
def delete_note(args: List[str], nb: Notebook):
    if not args:
        raise ValueError("Використання: delete-note <id>")
    id_val = int(args[0])
    if nb.delete(id_val):
        print(Fore.GREEN + f"Нотатку ID={id_val} видалено." + Style.RESET_ALL)
    else:
        print(Fore.RED + f"Нотатку ID={id_val} не знайдено." + Style.RESET_ALL)

@input_error
def sort_notes_by_date(args: List[str], nb: Notebook, abook: AddressBook = None):
    sorted_list = nb.sort_by_date()
    for note in sorted_list:
        block = format_note(note)
        if abook and note.contact_ids:
            contact_names = []
            for cid in note.contact_ids:
                try:
                    c = abook.find_by_id(cid)
                    contact_names.append(c.name)
                except KeyError:
                    pass
            if contact_names:
                lines = block.split("\n")
                lines.insert(1, f"{Fore.MAGENTA}Contacts:{Style.RESET_ALL} " + ", ".join(contact_names))
                block = "\n".join(lines)
        print_colored_box(f"Note ID={note.id}", block.split("\n"))

@input_error
def search_note_by_tag(args: List[str], nb: Notebook, abook: AddressBook = None):
    if not args:
        raise ValueError("Використання: search-tag <tag>")
    tag = args[0]
    results = nb.find_by_tag(tag)
    if not results:
        print(Fore.CYAN + f"Немає нотаток з тегом '{tag}'." + Style.RESET_ALL)
        return
    print(Fore.GREEN + f"Знайдено {len(results)} нотаток з тегом '{tag}':" + Style.RESET_ALL)
    for n in results:
        block = format_note(n)
        if abook and n.contact_ids:
            contact_names = []
            for cid in n.contact_ids:
                try:
                    c = abook.find_by_id(cid)
                    contact_names.append(c.name)
                except KeyError:
                    pass
            if contact_names:
                lines = block.split("\n")
                lines.insert(1, f"{Fore.MAGENTA}Contacts:{Style.RESET_ALL} " + ", ".join(contact_names))
                block = "\n".join(lines)
        print_colored_box(f"Note ID={n.id}", block.split("\n"))

@input_error
def search_note_by_date(args: List[str], nb: Notebook, abook: AddressBook = None):
    if not args:
        raise ValueError("Використання: search-date <YYYY-MM-DD>")
    date_str = args[0]
    results = nb.find_by_date(date_str)
    if not results:
        print(Fore.CYAN + f"Немає нотаток за датою {date_str}." + Style.RESET_ALL)
        return
    print(Fore.GREEN + f"Знайдено {len(results)} нотаток за {date_str}:" + Style.RESET_ALL)
    for n in results:
        block = format_note(n)
        if abook and n.contact_ids:
            contact_names = []
            for cid in n.contact_ids:
                try:
                    c = abook.find_by_id(cid)
                    contact_names.append(c.name)
                except KeyError:
                    pass
            if contact_names:
                lines = block.split("\n")
                lines.insert(1, f"{Fore.MAGENTA}Contacts:{Style.RESET_ALL} " + ", ".join(contact_names))
                block = "\n".join(lines)
        print_colored_box(f"Note ID={n.id}", block.split("\n"))

@input_error
def undo_note(args: List[str], nb: Notebook):
    msg = nb.undo()
    print(msg)

# ------------------------------------------------------
# Головна функція
# ------------------------------------------------------

def main():
    abook = AddressBook.load(CONTACTS_FILE)
    nbook = Notebook.load(NOTES_FILE)

    # Зверніть увагу: тепер ми в деякі функції передаємо кортеж (abook, nbook)
    COMMANDS = {
        # Контакти
        "add-contact": (lambda args: add_contact(args, abook, nbook)),
        "list-contacts": (lambda args: list_contacts(args, abook)),
        "search-contact": (lambda args: search_contact(args, abook)),
        "edit-contact": (lambda args: edit_contact(args, abook)),
        "delete-contact": (lambda args: delete_contact(args, abook, nbook)),
        "birthdays": (lambda args: upcoming_birthdays(args, abook)),
        "undo-contact": (lambda args: undo_contact(args, abook)),
        # Нотатки
        "add-note": (lambda args: add_note(args, nbook)),
        "list-notes": (lambda args: list_notes(args, nbook, abook)),
        "search-note": (lambda args: search_note(args, nbook, abook)),
        "edit-note": (lambda args: edit_note(args, nbook)),
        "delete-note": (lambda args: delete_note(args, nbook)),
        "sort-by-date": (lambda args: sort_notes_by_date(args, nbook, abook)),
        "search-tag": (lambda args: search_note_by_tag(args, nbook, abook)),
        "search-date": (lambda args: search_note_by_date(args, nbook, abook)),
        "undo-note": (lambda args: undo_note(args, nbook))
    }

    help_data_contacts = [
        ["add-contact", "Додати контакт (inline/інтерактивно), з можливістю створити нотатку"],
        ["list-contacts", "Список всіх контактів"],
        ["search-contact", "Пошук контакту за всіма полями"],
        ["edit-contact", "Редагувати контакт: edit-contact <id> поле=значення"],
        ["delete-contact", "Видалити контакт за ID (з обробкою пов'язаних нотаток)"],
        ["birthdays", "Показати контакти з ДН протягом 7 днів (days=N опціонально)"],
        ["undo-contact", "Скасувати останню дію з контактами"]
    ]

    help_data_notes = [
        ["add-note", "Додати нотатку (inline/інтерактивно)"],
        ["list-notes", "Список усіх нотаток (відображає прив'язані контакти)"],
        ["search-note", "Пошук нотатки (текст/теги + ім'я контакту)"],
        ["edit-note", "Редагувати нотатку: edit-note <id> поле=значення (text=, tags=, contact_ids=)"],
        ["delete-note", "Видалити нотатку за ID"],
        ["sort-by-date", "Сортувати нотатки за датою створення"],
        ["search-tag", "Пошук нотаток за тегом"],
        ["search-date", "Пошук нотаток за датою (YYYY-MM-DD)"],
        ["undo-note", "Скасувати останню дію з нотатками"]
    ]

    help_data_general = [
        ["help", "Вивести список команд"],
        ["exit", "Вийти з програми (зберегти дані)"],
        ["close", "Альтернативна команда виходу"]
    ]

    # Список команд для автодоповнення
    all_commands = list(COMMANDS.keys()) + ["help", "exit", "close"]
    command_completer = WordCompleter(all_commands, ignore_case=True)

    # Використовуємо чистий рядок для PromptSession
    session = PromptSession(">>> ", completer=command_completer)

    print(Fore.GREEN + "Вітаю! Це ваш персональний помічник." + Style.RESET_ALL)
    print("Наберіть 'help' для списку команд.")

    while True:
        user_input = session.prompt().strip()
        if not user_input:
            continue
        parts = user_input.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1].split() if len(parts) > 1 else []

        if command in ["exit", "close"]:
            print(Fore.YELLOW + "До побачення! Зберігаю дані..." + Style.RESET_ALL)
            # Зберігаємо дані перед виходом
            abook.save(CONTACTS_FILE)
            nbook.save(NOTES_FILE)
            break
        elif command == "help":
            print(format_help_table(help_data_contacts, "Contact Management"))
            print()
            print(format_help_table(help_data_notes, "Note Management"))
            print()
            print(format_help_table(help_data_general, "General"))
        elif command in COMMANDS:
            func = COMMANDS[command]
            func(args)
        else:
            suggestions = get_close_matches(command, all_commands, n=1)
            if suggestions:
                print(Fore.CYAN + f"Команду не знайдено. Можливо, ви мали на увазі: {suggestions[0]}?" + Style.RESET_ALL)
            else:
                print(Fore.RED + "Невідома команда. Спробуйте 'help' для списку команд." + Style.RESET_ALL)

if __name__ == "__main__":
    main()