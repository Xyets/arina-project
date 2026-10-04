from services.database import create_registration_code
import secrets


def generate_code():
    part1 = secrets.token_hex(2).upper()
    part2 = secrets.token_hex(2).upper()
    return f"MODEL-{part1}-{part2}"


if __name__ == "__main__":
    code = generate_code()
    create_registration_code(code)
    print()
    print("Новый код приглашения:")
    print(code)
    print()
    print("Передайте этот код нужной модели. Использовать его можно только один раз.")
