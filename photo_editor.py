"""
Простой фоторедактор.

Лабораторная работа 3.1, вариант 1: загрузка изображения, фильтр
"Оттенки серого", сохранение результата.
"""

import sys

import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from filters import apply_grayscale

# Текстовые значения пунктов выпадающего списка. Вариант 1 требует
# только "Оттенки серого" - "Оригинал" добавлен, чтобы можно было
# вернуться к исходному изображению без повторной загрузки файла.
FILTER_ORIGINAL = 'Оригинал'
FILTER_GRAYSCALE = 'Оттенки серого'

# Сторона, в которую вписывается превью (в пикселях), с сохранением
# пропорций - чтобы крупное фото не раздувало окно на весь экран.
PREVIEW_MAX_SIZE = 700


class PhotoEditor(QMainWindow):
    """Простой фоторедактор."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle('Фоторедактор')
        self.setGeometry(100, 100, 800, 650)

        # current_image - то, что загружено из файла (BGR, NumPy-массив,
        # как его возвращает cv2.imread). Остаётся неизменным при
        # применении фильтра - фильтр всегда применяется именно к нему,
        # а не к уже обработанному результату, иначе повторное нажатие
        # "Применить фильтр" накапливало бы эффект (например, размытие
        # поверх размытия).
        self.current_image = None

        # processed_image - результат последнего применения фильтра.
        # Именно его (а не current_image) сохраняет save_image().
        self.processed_image = None

        self.init_ui()

    def init_ui(self):
        """Инициализация интерфейса."""
        self.image_label = QLabel('Загрузите изображение')
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Минимальная высота - чтобы область превью не схлопывалась
        # в полоску до того, как в неё загрузят первое изображение.
        self.image_label.setMinimumHeight(400)

        self.load_button = QPushButton('Загрузить')

        self.filter_combo = QComboBox()
        self.filter_combo.addItems([FILTER_ORIGINAL, FILTER_GRAYSCALE])

        self.apply_button = QPushButton('Применить фильтр')
        self.save_button = QPushButton('Сохранить')

        self.load_button.clicked.connect(self.load_image)
        self.apply_button.clicked.connect(self.apply_filter)
        self.save_button.clicked.connect(self.save_image)

        layout = QVBoxLayout()
        layout.addWidget(self.image_label)
        layout.addWidget(self.load_button)
        layout.addWidget(self.filter_combo)
        layout.addWidget(self.apply_button)
        layout.addWidget(self.save_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def load_image(self):
        """Загружает изображение через диалог выбора файла."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Выберите изображение', '',
            'Изображения (*.jpg *.jpeg *.png *.bmp)'
        )

        # Пустой путь - пользователь нажал "Отмена". Штатная ситуация:
        # молча выходим, не трогая уже загруженное (если было) изображение.
        if not file_path:
            return

        # cv2.imread НЕ бросает исключение на отсутствующий, повреждённый
        # или неподдерживаемый файл - он просто молча возвращает None.
        # Это главная причина, по которой каждый вызов imread() в этом
        # файле сопровождается явной проверкой на None - без неё ошибка
        # проявится позже и куда менее понятно (например, AttributeError
        # внутри display_image при попытке прочитать .shape у None).
        image = cv2.imread(file_path)

        if image is None:
            QMessageBox.warning(
                self, 'Ошибка загрузки',
                f'Не удалось открыть файл как изображение:\n{file_path}\n\n'
                'Файл повреждён или имеет неподдерживаемый формат.'
            )
            return

        self.current_image = image
        # processed_image сбрасывается на свежезагруженный оригинал.
        # Если до этого уже был применён фильтр к ДРУГОЙ картинке,
        # кнопка "Сохранить" не должна случайно сохранить старый
        # результат поверх только что открытого нового изображения.
        self.processed_image = image.copy()
        self.filter_combo.setCurrentText(FILTER_ORIGINAL)
        self.display_image(image)

    def display_image(self, image):
        """Отображает NumPy-изображение (BGR) в image_label."""
        # OpenCV хранит изображение в порядке каналов BGR, а Qt (QImage)
        # ожидает RGB - без этой конвертации синий и красный цвета
        # поменялись бы местами на экране.
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        height, width, channels = rgb_image.shape
        # Число байт в одной строке изображения. QImage не вычисляет
        # это самостоятельно по одним только width/height, потому что
        # в общем случае строки в памяти могут быть выровнены с
        # дополнительными отступами - значение нужно передавать явно.
        bytes_per_line = channels * width

        qimage = QImage(
            rgb_image.data, width, height, bytes_per_line,
            QImage.Format.Format_RGB888,
        )

        pixmap = QPixmap.fromImage(qimage)
        # .scaled(..., KeepAspectRatio) вписывает изображение в область
        # предпросмотра, не искажая пропорции - иначе широкие фото
        # выглядели бы растянутыми или сплющенными по высоте.
        scaled_pixmap = pixmap.scaled(
            PREVIEW_MAX_SIZE, PREVIEW_MAX_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled_pixmap)

    def apply_filter(self):
        """Применяет выбранный в QComboBox фильтр к текущему изображению."""
        if self.current_image is None:
            QMessageBox.information(
                self, 'Нет изображения', 'Сначала загрузите изображение.'
            )
            return

        filter_name = self.filter_combo.currentText()

        if filter_name == FILTER_GRAYSCALE:
            result = apply_grayscale(self.current_image)
        else:
            # "Оригинал" - фильтр не применяется, просто показываем
            # исходное изображение заново.
            result = self.current_image

        # .copy() здесь обязателен: без него processed_image указывал
        # бы на ту же область памяти, что и result. Если бы в программу
        # позже добавили ещё обработку, изменяющую изображение "на
        # месте" (как делают многие функции OpenCV), это непреднамеренно
        # испортило бы и то, что должно было остаться сохранённым
        # результатом фильтра.
        self.processed_image = result.copy()
        self.display_image(result)

    def save_image(self):
        """Сохраняет обработанное изображение через диалог сохранения."""
        if self.processed_image is None:
            QMessageBox.information(
                self, 'Нечего сохранять',
                'Сначала загрузите изображение и примените фильтр.'
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, 'Сохранить изображение', '',
            'JPEG (*.jpg);;PNG (*.png);;Все файлы (*)'
        )

        if not file_path:
            return

        # cv2.imwrite тоже не бросает исключение при неудаче - как и
        # imread, она возвращает булево значение успеха (False, если,
        # например, указана несуществующая папка или формат, который
        # не удалось определить по расширению файла).
        success = cv2.imwrite(file_path, self.processed_image)

        if success:
            QMessageBox.information(
                self, 'Сохранено', f'Изображение сохранено:\n{file_path}'
            )
        else:
            QMessageBox.warning(
                self, 'Ошибка сохранения',
                f'Не удалось сохранить файл:\n{file_path}'
            )


def main():
    app = QApplication(sys.argv)
    window = PhotoEditor()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
