import json
import logging
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Type, TypeVar, Generic
from collections import UserDict, deque
import re

from abc import ABC, abstractmethod
from colorama import Fore, Style, init
from difflib import get_close_matches

# Ініціалізація colorama
init(autoreset=True)

# Логування
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
# ui.py (умовно)
# Кольорові і форматуючі функції для консольного виводу
# ------------------------------------------------------

def print_border(title: str = "", width: int = 60) -> None:
    """
    Друкує верхню рамку з опціональним заголовком.
    Наприклад, якщо title='Contact: John', то зліва/справа символи, а посередині title.
    """
    if title:
        # Відстань, яку ми виділяємо для заголовка, включаючи пробіли
        text_len = len(title) + 2
        if text_len > width - 4:
            text_len = width - 4
        # Сформувати рядок
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
    """
    Друкує нижню горизонтальну межу.
    """
    print(Fore.YELLOW + "─" * width + Style.RESET_ALL)


def indent_lines(lines: List[str], spaces: int = 2) -> str:
    """
    Додає задану кількість пробілів перед кожним рядком.
    """
    prefix = " " * spaces
    return "\n".join(prefix + line for line in lines)


def print_colored_box(header: str, lines: List[str], width: int = 60) -> None:
    """
    Друкує текст у кольоровій "рамці" з заголовком.
    """
    print_border(header, width)
    for line in lines:
        print(line)
    print_bottom_border(width)


def format_contact(contact: "Contact") -> str:
    """
    Повертає багаторядковий рядок з форматованим відображенням контакту.
    Використовується в print_colored_box при виводі.
    """
    # Поля контакту (всі можуть бути необов'язкові)
    lines = []
    lines.append(f"{Fore.CYAN}Name:{Style.RESET_ALL} {contact.name}")
    if contact.phones:
        lines.append(f"{Fore.CYAN}Phones:{Style.RESET_ALL}")
        for phone in contact.phones:
            lines.append(f"  {phone.value}")
    else:
        lines.append(f"{Fore.CYAN}Phones:{Style.RESET_ALL} (немає)")

    if contact.emails:
        lines.append(f"{Fore.CYAN}Emails:{Style.RESET_ALL}")
        for email in contact.emails:
            lines.append(f"  {email.value}")
    else:
        lines.append(f"{Fore.CYAN}Emails:{Style.RESET_ALL} (немає)")

    if contact.birthday:
        bday_str = contact.birthday_str()
        lines.append(f"{Fore.CYAN}Birthday:{Style.RESET_ALL} {bday_str}")
        days_to_bday = contact.days_to_birthday()
        age_val = contact.age()
        lines.append(f"  Days to next BDay: {days_to_bday if days_to_bday is not None else '-'}")
        lines.append(f"  Age: {age_val if age_val is not None else '-'}")
    else:
        lines.append(f"{Fore.CYAN}Birthday:{Style.RESET_ALL} (не вказано)")

    return "\n".join(lines)


def format_note(note: "Note") -> str:
    """
    Повертає багаторядковий рядок з форматованим відображенням нотатки.
    """
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
    """
    Приймає список зі списками: [[command, description], ...] і формує таблицю.
    """
    # Знаходимо макс. довжину команди
    max_cmd_len = max(len(row[0]) for row in commands_data)
    # Друкуємо рамку
    output_lines = []
    separator = "+" + "-"*(width-2) + "+"
    header_line = f"| {title.center(width-2)} |"
    output_lines.append(separator)
    output_lines.append(header_line)
    output_lines.append(separator)
    # Друкуємо рядки таблиці
    for cmd, desc in commands_data:
        # вирівнюємо команду
        # команди можна підсвітити іншим кольором, наприклад Fore.CYAN
        line = f"| {Fore.CYAN}{cmd:<{max_cmd_len}}{Style.RESET_ALL} : {desc}"
        # Довжина лівої частини: 2 + max_cmd_len + 3 (пропуск + двокрапка) = 5 + max_cmd_len
        # Перевіримо, чи не виходимо за межі width
        if len(line) > (width - 1):
            # Якщо виходить, переносимо опис на новий рядок, тощо.
            # Для спрощення припустимо, що воно влазить :)
            pass
        # Додаємо пропуски, аби заповнити до width-2 символів
        space_left = width - 2 - len(line)
        if space_left < 0:
            space_left = 0
        line += " " * space_left + "|"
        output_lines.append(line)
    output_lines.append(separator)
    return "\n".join(output_lines)

# ------------------------------------------------------
# models.py (умовно)
# Класи для даних: BaseEntry, Contact, Note
# ------------------------------------------------------

class Field:
    """
    Допоміжний клас, щоб інкапсулювати логіку валідації.
    Може бути у models.py або поруч із Contact/Note.
    """
    def __init__(self, value):
        self._value = value

    @property
    def value(self):
        return self._value


class Name(Field):
    def __init__(self, value: str):
        val = value.strip()
        if not val:
            raise ValueError("Ім'я не може бути порожнім.")
        super().__init__(val)


class Phone(Field):
    def __init__(self, value: str):
        val = value.strip()
        if not (val.isdigit() and len(val) == 10):
            raise ValueError("Телефон має складатися з 10 цифр.")
        super().__init__(val)


class Email(Field):
    def __init__(self, value: str):
        val = value.strip()
        pattern = r"[^@]+@[^@]+\.[^@]+"
        if not re.match(pattern, val):
            raise ValueError("Неправильний формат Email.")
        super().__init__(val)


# Абстрактний базовий клас для записів
class BaseEntry(ABC):
    """
    Базовий клас для будь-якого "запису" в системі.
    Має принаймні поле id і методи:
    - to_dict(): Dict[str, any]
    - from_dict(cls, data: dict) -> BaseEntry
    - matches(query: str): bool
    - update(**fields)
    """
    def __init__(self, id: int):
        self.id = id

    @abstractmethod
    def to_dict(self) -> dict:
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> "BaseEntry":
        pass

    @abstractmethod
    def matches(self, query: str) -> bool:
        """
        Повертає True, якщо поле запису містить підрядок query 
        (наприклад, name, phone, text, tag і т.д.)
        """
        pass

    @abstractmethod
    def update(self, **fields):
        """
        Оновлення різних полів запису з переданих аргументів.
        """
        pass


class Contact(BaseEntry):
    """
    Клас для контакту (адресної книги).
    Поля: name: Name, phones: List[Phone], emails: List[Email], birthday (date)
    """
    def __init__(self,
                 id: int,
                 name: str,
                 phones: Optional[List[str]] = None,
                 emails: Optional[List[str]] = None,
                 birthday: Optional[str] = None):
        super().__init__(id)
        self.name = Name(name)
        self.phones: List[Phone] = []
        if phones:
            for p in phones:
                self.phones.append(Phone(p))
        self.emails: List[Email] = []
        if emails:
            for e in emails:
                self.emails.append(Email(e))
        self._birthday: Optional[date] = None
        if birthday:
            self.set_birthday(birthday)

    def set_birthday(self, birthday_str: str):
        """
        Парсить рядок (DD.MM.YYYY або YYYY-MM-DD) і зберігає date object.
        """
        fmt_candidates = ["%d.%m.%Y", "%Y-%m-%d"]
        parsed = None
        for fmt in fmt_candidates:
            try:
                parsed = datetime.strptime(birthday_str, fmt).date()
                break
            except ValueError:
                continue
        if not parsed:
            raise ValueError("Дата народження в неправильному форматі (спробуйте DD.MM.YYYY).")
        self._birthday = parsed

    def birthday_str(self) -> str:
        if not self._birthday:
            return ""
        return self._birthday.strftime("%d.%m.%Y")

    def days_to_birthday(self) -> Optional[int]:
        if not self._birthday:
            return None
        today = date.today()
        bday = self._birthday.replace(year=today.year)
        if bday < today:
            bday = bday.replace(year=today.year + 1)
        return (bday - today).days

    def age(self) -> Optional[int]:
        if not self._birthday:
            return None
        today = date.today()
        return today.year - self._birthday.year - \
            ((today.month, today.day) < (self._birthday.month, self._birthday.day))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name.value,
            "phones": [p.value for p in self.phones],
            "emails": [e.value for e in self.emails],
            "birthday": self._birthday.strftime("%Y-%m-%d") if self._birthday else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Contact":
        return cls(
            id=data["id"],
            name=data["name"],
            phones=data.get("phones", []),
            emails=data.get("emails", []),
            birthday=data.get("birthday", None)
        )

    def matches(self, query: str) -> bool:
        query_lower = query.lower()
        # Перевіряємо в name, phones, emails
        if query_lower in self.name.value.lower():
            return True
        for p in self.phones:
            if query_lower in p.value.lower():
                return True
        for e in self.emails:
            if query_lower in e.value.lower():
                return True
        # Якщо є день народження, то можна і його перевірити
        if self._birthday and query_lower in self.birthday_str():
            return True
        return False

    def update(self, **fields):
        """
        Оновлення даних контакту. Допускаємо, що поля:
        name, phones(list of str), emails(list of str), birthday(str).
        """
        if "name" in fields:
            self.name = Name(fields["name"])
        if "phones" in fields:
            self.phones = [Phone(p) for p in fields["phones"]]
        if "emails" in fields:
            self.emails = [Email(e) for e in fields["emails"]]
        if "birthday" in fields:
            self.set_birthday(fields["birthday"])


class Note(BaseEntry):
    """
    Клас для нотатки.
    Поля: text: str, tags: List[str], created_at: datetime
    """
    def __init__(self,
                 id: int,
                 text: str,
                 tags: Optional[List[str]] = None,
                 created_at: Optional[datetime] = None):
        super().__init__(id)
        self.text = text
        self.tags = tags if tags else []
        self.created_at = created_at if created_at else datetime.now()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "tags": self.tags,
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
            created_at=created_dt
        )

    def matches(self, query: str) -> bool:
        query_lower = query.lower()
        if query_lower in self.text.lower():
            return True
        for tag in self.tags:
            if query_lower in tag.lower():
                return True
        return False

    def update(self, **fields):
        """
        Оновлює текст і/або теги.
        Наприклад, text="new text", tags=["tag1","tag2"].
        """
        if "text" in fields:
            self.text = fields["text"]
        if "tags" in fields:
            self.tags = fields["tags"]


# ------------------------------------------------------
# collections.py (умовно)
# Універсальний клас BaseBook, та його підкласи
# ------------------------------------------------------

E = TypeVar("E", bound=BaseEntry)

class BaseBook(UserDict, Generic[E]):
    """
    Узагальнена колекція об'єктів BaseEntry.
    Зберігає в self.data {id: entry}, де entry - нащадок BaseEntry.
    """
    entry_class: Type[E] = BaseEntry  # визначається в підкласах
    entry_type_name: str = "entry"    # для повідомлень

    def __init__(self):
        super().__init__()
        self.undo_stack = deque(maxlen=MAX_UNDO_STEPS)
        self._max_id = 0  # щоб відслідковувати найбільший використаний ID

    def add(self, entry: E) -> int:
        """
        Додає об'єкт у колекцію. Якщо entry.id = 0,
        призначаємо новий ID = _max_id + 1.
        Додаємо операцію в undo_stack.
        """
        if entry.id == 0:
            entry.id = self._max_id + 1
        self._max_id = max(self._max_id, entry.id)
        self.undo_stack.append(("add", entry.id, None))
        self.data[entry.id] = entry
        return entry.id

    def create_and_add(self, **kwargs) -> int:
        """
        Створює новий запис типу self.entry_class з переданими полями,
        додає до книги та повертає ID запису.
        """
        # Для Contact: name, phones, emails, birthday...
        # Для Note: text, tags...
        # 'id=0' - передаємо 0, щоб система сама призначила.
        entry = self.entry_class(id=0, **kwargs)
        return self.add(entry)

    def find_by_id(self, id_val: int) -> E:
        if id_val not in self.data:
            raise KeyError(f"{self.entry_type_name} with ID={id_val} not found.")
        return self.data[id_val]

    def find(self, query: str) -> List[E]:
        """
        Повертає список записів, що задовольняють matches(query).
        """
        results = []
        for entry in self.data.values():
            if entry.matches(query):
                results.append(entry)
        return results

    def edit(self, id_val: int, **changes) -> None:
        """
        Редагує запис з ID=id_val, зберігаючи стару копію для undo.
        """
        old_entry = self.data.get(id_val)
        if not old_entry:
            raise KeyError(f"{self.entry_type_name} with ID={id_val} not found.")
        # Для undo зберігаємо клон (можна зробити більш глибоке копіювання),
        # наприклад, створюємо новий entry_class з даними old_entry.to_dict().
        old_data = old_entry.to_dict()
        old_copy = self.entry_class.from_dict(old_data)
        self.undo_stack.append(("edit", id_val, old_copy))
        # Оновлюємо поля
        old_entry.update(**changes)

    def delete(self, id_val: int) -> bool:
        if id_val in self.data:
            old_entry = self.data[id_val]
            self.undo_stack.append(("delete", id_val, old_entry))
            del self.data[id_val]
            return True
        return False

    def undo(self) -> str:
        """
        Скасовує останню операцію (add, delete, edit).
        """
        if not self.undo_stack:
            return "Немає дій для скасування."
        action, id_val, old_value = self.undo_stack.pop()
        if action == "add":
            # при add old_value = None, треба видалити запис
            if id_val in self.data:
                del self.data[id_val]
            return f"Скасовано додавання {self.entry_type_name} з ID {id_val}."
        elif action == "delete":
            # відновлюємо old_value
            self.data[id_val] = old_value
            return f"Відновлено {self.entry_type_name} з ID {id_val}."
        elif action == "edit":
            # замінюємо поточний entry на old_value
            self.data[id_val] = old_value
            return f"Скасовано редагування {self.entry_type_name} з ID {id_val}."
        return "Невідома операція для undo."

    def save(self, filename: str):
        """
        Зберігає self.data у JSON-файл, викликаючи to_dict() для кожного запису.
        """
        save_dict = {}
        for eid, entry in self.data.items():
            save_dict[str(eid)] = entry.to_dict()
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(save_dict, f, ensure_ascii=False, indent=4)

    @classmethod
    def load(cls, filename: str) -> "BaseBook":
        """
        Завантажує записи з файлу, створює новий BaseBook.
        """
        new_book = cls()
        try:
            with open(filename, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print(Fore.YELLOW + f"Файл {filename} не знайдено або пошкоджено. Створено порожню книгу." + Style.RESET_ALL)
            return new_book
        # Відновлюємо об'єкти
        for k, v in raw.items():
            eid = int(k)
            entry = cls.entry_class.from_dict(v)
            new_book.data[eid] = entry
            if eid > new_book._max_id:
                new_book._max_id = eid
        return new_book


class AddressBook(BaseBook[Contact]):
    entry_class = Contact
    entry_type_name = "контакт"

    def get_upcoming_birthdays(self, days_ahead: int = 7) -> List[Contact]:
        """
        Повертає всі контакти, у яких День Народження настане упродовж
        наступних days_ahead днів. 
        Перевірка з урахуванням переносу на наступний рік, якщо вже минув у цьому.
        """
        today = date.today()
        result = []
        for c in self.data.values():
            if not c._birthday:
                continue
            bday_this_year = c._birthday.replace(year=today.year)
            if bday_this_year < today:
                bday_this_year = bday_this_year.replace(year=today.year + 1)
            diff = (bday_this_year - today).days
            if 0 <= diff < days_ahead:
                result.append(c)
        return result


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


# ------------------------------------------------------
# cli.py (умовно)
# Функції - команди для користувача
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
            logging.error(f"IndexError in {func.__name__}: Not enough arguments.")
            print(Fore.RED + "Неправильний формат команди або недостатньо аргументів." + Style.RESET_ALL)
        except Exception as e:
            logging.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            print(Fore.RED + f"Сталася несподівана помилка: {e}" + Style.RESET_ALL)
    return wrapper


@input_error
def add_contact(args: List[str], abook: AddressBook):
    """
    add-contact John 1234567890 email@domain.com ...
    """
    if len(args) < 2:
        raise ValueError("Використання: add-contact <name> <phone> [email1 email2 ...]")
    name = args[0]
    phone = args[1]
    emails = args[2:] if len(args) > 2 else []
    # створюємо контакт і додаємо
    new_id = abook.create_and_add(
        name=name,
        phones=[phone],
        emails=emails
    )
    contact_obj = abook.find_by_id(new_id)
    # Красиво виведемо
    from_ui = format_contact(contact_obj)
    print_colored_box(f"Contact added (ID={new_id})", from_ui.split("\n"))


@input_error
def list_contacts(args: List[str], abook: AddressBook):
    """
    list-contacts
    Показує всі контакти в детальному форматі.
    """
    if not abook.data:
        print(Fore.YELLOW + "У книзі немає контактів." + Style.RESET_ALL)
        return
    print(Fore.GREEN + f"Усього контактів: {len(abook.data)}" + Style.RESET_ALL)
    for c in abook.data.values():
        block = format_contact(c)
        print_colored_box(f"Contact ID={c.id}", block.split("\n"))


@input_error
def search_any(args: List[str], abook: AddressBook):
    """
    search-contact <query>
    Пошук у всіх полях контакту.
    """
    if not args:
        raise ValueError("Використання: search-contact <query>")
    query = " ".join(args)
    results = abook.find(query)
    if not results:
        print(Fore.CYAN + "Нічого не знайдено." + Style.RESET_ALL)
        return
    print(Fore.GREEN + f"Знайдено {len(results)} результ. за '{query}':" + Style.RESET_ALL)
    for c in results:
        block = format_contact(c)
        print_colored_box(f"Contact ID={c.id}", block.split("\n"))


@input_error
def edit_contact(args: List[str], abook: AddressBook):
    """
    edit-contact <id> name="New Name" phones="0987654321,0501234567" emails="new@domain.com"
    birthday="01.01.2000"
    Приклад:
        edit-contact 1 name="Ivan Petrov" phones="1234567890" 
    """
    if len(args) < 2:
        raise ValueError("Використання: edit-contact <id> поле1=значення1 ...")

    id_val = int(args[0])
    changes = {}
    for chunk in args[1:]:
        if "=" in chunk:
            key, val = chunk.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key in ("phones", "emails"):
                # припустимо, користувач передає коми: "phone1,phone2"
                arr = [x.strip() for x in val.split(",")]
                changes[key] = arr
            else:
                changes[key] = val

    abook.edit(id_val, **changes)
    print(Fore.GREEN + f"Контакт ID={id_val} відредаговано." + Style.RESET_ALL)


@input_error
def delete_contact(args: List[str], abook: AddressBook):
    """
    delete-contact <id>
    """
    if not args:
        raise ValueError("Використання: delete-contact <id>")
    id_val = int(args[0])
    ok = abook.delete(id_val)
    if ok:
        print(Fore.GREEN + f"Контакт ID={id_val} видалено." + Style.RESET_ALL)
    else:
        print(Fore.RED + f"Контакт ID={id_val} не знайдено." + Style.RESET_ALL)


@input_error
def upcoming_birthdays(args: List[str], abook: AddressBook):
    """
    upcoming-birthdays [days=7]
    """
    days = 7
    if args and args[0].startswith("days="):
        parts = args[0].split("=", 1)
        days = int(parts[1])
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

# ------- Нотатки

@input_error
def add_note(args: List[str], nb: Notebook):
    """
    add-note <text> [#tag1 #tag2 ...]
    """
    if not args:
        raise ValueError("Використання: add-note <text> [#tag1 #tag2 ...]")
    text_parts = []
    tags = []
    for arg in args:
        if arg.startswith('#'):
            tags.append(arg[1:])
        else:
            text_parts.append(arg)
    text = " ".join(text_parts)
    if not text:
        raise ValueError("Текст нотатки не може бути порожнім.")
    new_id = nb.create_and_add(text=text, tags=tags)
    note = nb.find_by_id(new_id)
    block = format_note(note)
    print_colored_box(f"Note added (ID={new_id})", block.split("\n"))


@input_error
def list_notes(args: List[str], nb: Notebook):
    """
    list-notes
    """
    if not nb.data:
        print(Fore.YELLOW + "Нотаток ще немає." + Style.RESET_ALL)
        return
    print(Fore.GREEN + f"Усього нотаток: {len(nb.data)}" + Style.RESET_ALL)
    for note in nb.data.values():
        block = format_note(note)
        print_colored_box(f"Note ID={note.id}", block.split("\n"))


@input_error
def search_notes(args: List[str], nb: Notebook):
    """
    search-note <query>
    """
    if not args:
        raise ValueError("Використання: search-note <query>")
    query = " ".join(args)
    results = nb.find(query)
    if not results:
        print(Fore.CYAN + "Нічого не знайдено." + Style.RESET_ALL)
        return
    print(Fore.GREEN + f"Знайдено {len(results)} нотаток за '{query}':" + Style.RESET_ALL)
    for n in results:
        block = format_note(n)
        print_colored_box(f"Note ID={n.id}", block.split("\n"))


@input_error
def edit_note(args: List[str], nb: Notebook):
    """
    edit-note <id> text="New text" tags="#shop,#todo"
    """
    if len(args) < 2:
        raise ValueError("Використання: edit-note <id> field=val ...")
    id_val = int(args[0])
    changes = {}
    for chunk in args[1:]:
        if "=" in chunk:
            key, val = chunk.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key == "tags":
                # якщо користувач дав "#shop,#todo"
                # вилучимо '#' і розіб'ємо за комами
                arr = [x.strip().lstrip('#') for x in val.split(",")]
                changes[key] = arr
            else:
                changes[key] = val

    nb.edit(id_val, **changes)
    print(Fore.GREEN + f"Нотатку ID={id_val} відредаговано." + Style.RESET_ALL)


@input_error
def delete_note(args: List[str], nb: Notebook):
    """
    delete-note <id>
    """
    if not args:
        raise ValueError("Використання: delete-note <id>")
    id_val = int(args[0])
    ok = nb.delete(id_val)
    if ok:
        print(Fore.GREEN + f"Нотатку ID={id_val} видалено." + Style.RESET_ALL)
    else:
        print(Fore.RED + f"Нотатку ID={id_val} не знайдено." + Style.RESET_ALL)


@input_error
def sort_notes_by_date(args: List[str], nb: Notebook):
    sorted_list = nb.sort_by_date()
    for note in sorted_list:
        block = format_note(note)
        print_colored_box(f"Note ID={note.id}", block.split("\n"))


@input_error
def search_note_by_tag(args: List[str], nb: Notebook):
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
        print_colored_box(f"Note ID={n.id}", block.split("\n"))


@input_error
def search_note_by_date(args: List[str], nb: Notebook):
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
        print_colored_box(f"Note ID={n.id}", block.split("\n"))


@input_error
def undo_note(args: List[str], nb: Notebook):
    msg = nb.undo()
    print(msg)

# ------------------------------------------------------
# Головна функція
# ------------------------------------------------------

def main():
    # Завантажуємо книги
    abook = AddressBook.load(CONTACTS_FILE)
    nbook = Notebook.load(NOTES_FILE)

    COMMANDS = {
        # Контакти
        "add-contact": (add_contact, abook),
        "list-contacts": (list_contacts, abook),
        "search-contact": (search_any, abook),
        "edit-contact": (edit_contact, abook),
        "delete-contact": (delete_contact, abook),
        "birthdays": (upcoming_birthdays, abook),
        "undo-contact": (undo_contact, abook),
        # Нотатки
        "add-note": (add_note, nbook),
        "list-notes": (list_notes, nbook),
        "search-note": (search_notes, nbook),
        "edit-note": (edit_note, nbook),
        "delete-note": (delete_note, nbook),
        "sort-by-date": (sort_notes_by_date, nbook),
        "search-tag": (search_note_by_tag, nbook),
        "search-date": (search_note_by_date, nbook),
        "undo-note": (undo_note, nbook)
    }

    help_data_contacts = [
        ["add-contact", "Додати контакт: add-contact <name> <phone> [email1 ...]"],
        ["list-contacts", "Список всіх контактів"],
        ["search-contact", "Пошук контакту за усіма полями"],
        ["edit-contact", "Редагувати контакт (name=..., phones=..., emails=..., birthday=...)"],
        ["delete-contact", "Видалити контакт за ID"],
        ["birthdays", "Показати контакти, у яких ДН у найближчі 7 днів"],
        ["undo-contact", "Скасувати останню операцію з контактами"]
    ]

    help_data_notes = [
        ["add-note", "Додати нотатку: add-note <text> [#tag1 ...]"],
        ["list-notes", "Список усіх нотаток"],
        ["search-note", "Пошук нотаток за текстом або тегами"],
        ["edit-note", "Редагувати нотатку (text=..., tags=...)"],
        ["delete-note", "Видалити нотатку за ID"],
        ["sort-by-date", "Сортувати нотатки за датою створення"],
        ["search-tag", "Шукати нотатки за тегом"],
        ["search-date", "Шукати нотатки за датою (YYYY-MM-DD)"],
        ["undo-note", "Скасувати останню операцію з нотатками"]
    ]

    help_data_general = [
        ["help", "Вивести список команд"],
        ["exit", "Вийти з програми (зберегти дані)"],
        ["close", "Альтернативна команда виходу"]
    ]

    print(Fore.GREEN + "Вітаю! Це ваш персональний помічник." + Style.RESET_ALL)
    print("Наберіть 'help' для списку команд.")

    while True:
        user_input = input(Fore.CYAN + ">>> " + Style.RESET_ALL).strip()
        if not user_input:
            continue
        parts = user_input.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1].split() if len(parts) > 1 else []

        if command in ["exit", "close"]:
            print(Fore.YELLOW + "До побачення! Зберігаю дані..." + Style.RESET_ALL)
            # зберігаємо
            abook.save(CONTACTS_FILE)
            nbook.save(NOTES_FILE)
            break
        elif command == "help":
            # Виводимо help - 3 таблиці
            print(format_help_table(help_data_contacts, "Contact Management"))
            print()
            print(format_help_table(help_data_notes, "Note Management"))
            print()
            print(format_help_table(help_data_general, "General"))
        elif command in COMMANDS:
            func, target = COMMANDS[command]
            func(args, target)  # виклик із параметрами
        else:
            # Спробувати знайти найближчий збіг команди
            suggestions = get_close_matches(command, list(COMMANDS.keys()) + ["exit", "help", "close"], n=1)
            if suggestions:
                print(Fore.CYAN + f"Команду не знайдено. Можливо, ви мали на увазі: {suggestions[0]}?" + Style.RESET_ALL)
            else:
                print(Fore.RED + "Невідома команда. Спробуйте 'help' для списку команд." + Style.RESET_ALL)


if __name__ == "__main__":
    main()
