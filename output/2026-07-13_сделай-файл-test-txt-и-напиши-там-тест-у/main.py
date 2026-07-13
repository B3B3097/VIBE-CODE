def create_test_file():
    """
    Создает файл test.txt и записывает в него строку "Тест успешный".
    
    Returns:
        None
    
    Raises:
        Exception: Если произошла ошибка при создании файла.
    """
    try:
        with open('test.txt', 'w', encoding='utf-8') as file:
            file.write("Тест успешный")
        print("Файл test.txt создан успешно.")
    except Exception as e:
        print(f"Ошибка при создании файла: {e}")
        raise

if __name__ == "__main__":
    create_test_file()