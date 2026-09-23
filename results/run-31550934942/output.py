Конечно! Вот пример простого калькулятора на Python. Этот код можно использовать как основу для более сложных приложений.

```python
def add(x, y):
    return x + y

def subtract(x, y):
    return x - y

def multiply(x, y):
    return x * y

def divide(x, y):
    if y == 0:
        return "Ошибка! Деление на ноль."
    else:
        return x / y

def calculator():
    print("Выберите операцию:")
    print("1. Сложение")
    print("2. Вычитание")
    print("3. Умножение")
    print("4. Деление")

    while True:
        choice = input("Введите номер операции (1/2/3/4): ")

        if choice in ['1', '2', '3', '4']:
            try:
                num1 = float(input("Введите первое число: "))
                num2 = float(input("Введите второе число: "))
            except ValueError:
                print("Ошибка! Введите числовые значения.")
                continue

            if choice == '1':
                print(f"{num1} + {num2} = {add(num1, num2)}")

            elif choice == '2':
                print(f"{num1} - {num2} = {subtract(num1, num2)}")

            elif choice == '3':
                print(f"{num1} * {num2} = {multiply(num1, num2)}")

            elif choice == '4':
                result = divide(num1, num2)
                print(f"{num1} / {num2} = {result}")

        else:
            print("Ошибка! Неверный выбор. Попробуйте снова.")

        next_calculation = input("Хотите выполнить еще одну операцию? (да/нет): ")
        if next_calculation.lower() != 'да':
            break

if __name__ == "__main__":
    calculator()
```

Этот код реализует базовый калькулятор с четырьмя основными операциями: сложение, вычитание, умножение и деление. Пользователь может выбирать операцию, вводить числа и получать результат.

Для запуска этого кода вам нужно будет сохранить его в файле с расширением `.py` (например, `calculator.py`) и выполнить его с помощью интерпретатора Python.