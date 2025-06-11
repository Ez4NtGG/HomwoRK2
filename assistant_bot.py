import os
import pickle
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import csv

def input_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as ve:
            return str(ve)
        except IndexError:
            return "Please provide all necessary arguments."
        except KeyError:
            return "Contact not found."
        except Exception as e:
            return f"An unexpected error occurred: {e}"
    return wrapper

class Field:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)

class Name(Field):
    pass

class Phone(Field):
    def __init__(self, value):
        cleaned = value.replace("+", "").replace("-", "").replace(" ", "")
        if not cleaned.isdigit() or len(cleaned) not in (10, 12):
            raise ValueError("Phone number must contain 10–12 digits (with optional '+' prefix).")
        super().__init__(cleaned)

class Birthday(Field):
    def __init__(self, value):
        try:
            datetime.strptime(value, "%d.%m.%Y")
            super().__init__(value)
        except ValueError:
            raise ValueError("Invalid date format. Use DD.MM.YYYY")

class Record:
    def __init__(self, name: str, phone: str | None = None, email: str = ""):
        self.name = Name(name)
        self.phones: list[Phone] = []
        if phone:
            self.add_phone(phone)
        self.email = email
        self.birthday: Birthday | None = None

    def add_phone(self, phone: str):
        self.phones.append(Phone(phone))

    def remove_phone(self, phone: str):
        self.phones = [p for p in self.phones if p.value != phone]

    def edit_phone(self, old_phone: str, new_phone: str):
        for p in self.phones:
            if p.value == old_phone:
                p.value = Phone(new_phone).value  
                return "Phone updated."
        raise ValueError("Old phone number not found.")

    def find_phone(self, phone: str) -> Phone | None:
        return next((p for p in self.phones if p.value == phone), None)

    def add_birthday(self, birthday: str):
        self.birthday = Birthday(birthday)

    def __str__(self):
        phones = "; ".join(str(p) for p in self.phones) if self.phones else "<no phones>"
        email_part = f", email: {self.email}" if self.email else ""
        bday_part = f", birthday: {self.birthday}" if self.birthday else ""
        return f"{self.name}: {phones}{email_part}{bday_part}"

class AddressBook:
    FILENAME = "addressbook.pkl"

    def __init__(self):
        self.data: dict[str, Record] = {}

    def add_record(self, record: Record):
        self.data[record.name.value] = record

    def find(self, name: str) -> Record | None:
        return self.data.get(name)

    def delete(self, name: str):
        self.data.pop(name, None)

    def get_upcoming_birthdays(self):
        today = datetime.today().date()
        upcoming: list[dict[str, str]] = []

        for rec in self.data.values():
            if not rec.birthday:
                continue
            bday_date = datetime.strptime(rec.birthday.value, "%d.%m.%Y").date()
            bday_this_year = bday_date.replace(year=today.year)
            if bday_this_year < today:
                bday_this_year = bday_this_year.replace(year=today.year + 1)

            days = (bday_this_year - today).days
            if 0 <= days <= 7:

                if bday_this_year.weekday() >= 5:
                    bday_this_year += timedelta(days=7 - bday_this_year.weekday())
                upcoming.append({"name": rec.name.value, "birthday": bday_this_year.strftime("%d.%m.%Y")})

        return upcoming

    def save(self, filename: str | None = None):
        filename = filename or self.FILENAME
        with open(filename, "wb") as fh:
            pickle.dump(self.data, fh)

    def load(self, filename: str | None = None):
        filename = filename or self.FILENAME
        try:
            with open(filename, "rb") as fh:
                self.data = pickle.load(fh)
        except (FileNotFoundError, pickle.PickleError):
            self.data = {}

    def export_to_csv(self, filename="contacts.csv"):
        with open(filename, mode="w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Name", "Phones", "Email", "Birthday"])
            for rec in self.data.values():
                writer.writerow([
                    rec.name.value,
                    "; ".join(p.value for p in rec.phones),
                    rec.email,
                    rec.birthday.value if rec.birthday else ""
                ])

    def __iter__(self):
        return iter(self.data.values())

    def __repr__(self):
        if not self.data:
            return "Address book is empty"
        return "\n".join(f"{i+1}. {rec}" for i, rec in enumerate(self.data.values()))

class UserView(ABC):
    @abstractmethod
    def prompt(self, message: str) -> str:
        pass

    @abstractmethod
    def show_message(self, message: str):
        pass

    @abstractmethod
    def display_contacts(self, records: list[Record]):
        pass

    @abstractmethod
    def display_help(self):
        pass

class ConsoleUserView(UserView):
    def prompt(self, message: str) -> str:
        return input(message)

    def show_message(self, message: str):
        print(message)

    def display_contacts(self, records: list[Record]):
        if not records:
            print("No contacts found.")
            return
        print("\nКонтакти:")
        for rec in records:
            print(f" - {rec}")
        print()

    def display_help(self):
        print("""
Available commands:
  hello                       – greet bot
  add <name> <phone> [email]  – add / update contact
  change <name> <old> <new>   – change phone
  phone <name>                – show phones
  all                         – list all contacts
  add-birthday <name> <D.M.Y> – add birthday
  show-birthday <name>        – show birthday
  birthdays                   – next week's birthdays
  export                      – export contacts to CSV
  help                        – show this help
  exit | close                – save & quit
""")

class AddressBookController:
    def __init__(self, book: AddressBook, view: UserView):
        self.book = book
        self.view = view
        self.commands = {
            "hello": self.cmd_hello,
            "add": self.cmd_add,
            "change": self.cmd_change,
            "phone": self.cmd_phone,
            "all": self.cmd_all,
            "add-birthday": self.cmd_add_birthday,
            "show-birthday": self.cmd_show_birthday,
            "birthdays": self.cmd_birthdays,
            "export": self.cmd_export,
            "help": self.cmd_help,
            "exit": self.cmd_exit,
            "close": self.cmd_exit,
        }
        self.running = True

    def cmd_hello(self, *_):
        self.view.show_message("How can I help you?")

    @input_error
    def cmd_add(self, *args):
        if len(args) < 2:
            raise ValueError("Usage: add <name> <phone> [email]")
        name, phone, *rest = args
        email = rest[0] if rest else ""
        record = self.book.find(name)
        if record is None:
            record = Record(name, phone, email)
            self.book.add_record(record)
            self.view.show_message("Contact added.")
        else:
            record.add_phone(phone)
            if email:
                record.email = email
            self.view.show_message("Contact updated.")

    @input_error
    def cmd_change(self, *args):
        if len(args) != 3:
            raise ValueError("Usage: change <name> <old_phone> <new_phone>")
        name, old_phone, new_phone = args
        rec = self.book.find(name)
        if rec:
            msg = rec.edit_phone(old_phone, new_phone)
            self.view.show_message(msg)
        else:
            raise ValueError(f"Contact {name} not found.")

    @input_error
    def cmd_phone(self, *args):
        if len(args) != 1:
            raise ValueError("Usage: phone <name>")
        name = args[0]
        rec = self.book.find(name)
        if rec and rec.phones:
            self.view.show_message(f"{name}: {', '.join(str(p) for p in rec.phones)}")
        else:
            raise ValueError(f"No phone found for {name}.")

    def cmd_all(self, *_):
        self.view.display_contacts(list(self.book))

    @input_error
    def cmd_add_birthday(self, *args):
        if len(args) != 2:
            raise ValueError("Usage: add-birthday <name> <DD.MM.YYYY>")
        name, bday = args
        rec = self.book.find(name)
        if rec:
            rec.add_birthday(bday)
            self.view.show_message("Birthday added.")
        else:
            raise ValueError(f"Contact {name} not found.")

    @input_error
    def cmd_show_birthday(self, *args):
        if len(args) != 1:
            raise ValueError("Usage: show-birthday <name>")
        name = args[0]
        rec = self.book.find(name)
        if rec and rec.birthday:
            self.view.show_message(f"{name}'s birthday is {rec.birthday.value}")
        else:
            raise ValueError(f"No birthday found for {name}.")

    def cmd_birthdays(self, *_):
        upcoming = self.book.get_upcoming_birthdays()
        if not upcoming:
            self.view.show_message("No upcoming birthdays in the next week.")
        else:
            lines = [f"{e['name']}: {e['birthday']}" for e in upcoming]
            self.view.show_message("\n".join(lines))

    def cmd_export(self, *_):
        self.book.export_to_csv()
        self.view.show_message("Contacts exported to contacts.csv")

    def cmd_help(self, *_):
        self.view.display_help()

    def cmd_exit(self, *_):
        self.book.save()
        self.view.show_message("Data saved. Bye!")
        self.running = False

    def parse_input(self, raw: str):
        parts = raw.strip().split()
        if not parts:
            return "", []
        return parts[0].lower(), parts[1:]

    def run(self):
        self.view.display_help()
        while self.running:
            cmd_line = self.view.prompt("> ")
            cmd, args = self.parse_input(cmd_line)
            handler = self.commands.get(cmd)
            if handler:
                handler(*args)
            elif cmd.strip():
                self.view.show_message("Unknown command. Type 'help' for options.")

def main():
    view = ConsoleUserView()
    model = AddressBook()
    model.load()  # load persisted data if any
    controller = AddressBookController(model, view)
    try:
        controller.run()
    except KeyboardInterrupt:
        controller.cmd_exit()

if __name__ == "__main__":
    main()
