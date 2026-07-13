def write_test_file():
    """
    Writes 'Тест успешный' to a file named 'test.txt'.
    
    Returns:
        None
    
    Raises:
        IOError: If there's an error opening or writing to the file.
    """
    try:
        with open('test.txt', 'w', encoding='utf-8') as file:
            file.write('Тест успешный')
        print("Файл успешно создан и заполнен.")
    except IOError as e:
        print(f"Ошибка при создании или записи файла: {e}")

if __name__ == "__main__":
    write_test_file()