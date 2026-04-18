[PL below]
# GMTB – Geological Mapping ToolBox

**Author:** Karolina Kucharz
**Version:** 1.1.0

A Python Toolbox for the ArcGIS Pro environment, designed to automate key tasks in the field of digital geological mapping. 
The project was developed as part of a thesis at the Faculty of Geology, Geophysics, and Environmental Protection at the Stanisław Staszic University of Science and Technology in Kraków.

## Description

GMTB automates processes that typically require many manual steps, offering an integrated and intuitive analytical workflow. The Toolbox consists of two main, complementary tools.

### Key Features

*   **“Generate Intersection Lines” Tool**
    *   Modeling geological planes based on input data.
    *   Support for two methods of defining a plane:
        1.  **1-Point with Orientation Method:** For visualizing known measurements (Dip/Dir).
        2.  **3-Point Method:** For calculating unknown orientation based on points.
    *   Automatic generation of a vector intersection line between the plane and the Digital Elevation Model (DEM).
    *   Creation of a geological surface in TIN format.


*   **“Calculate Thickness” Tool**
    *   Calculates apparent and actual thickness based on two intersecting lines.
    *   Offers three analysis modes:
        1.  **Local:** Precise measurement at a point specified by the user.
        2.  **Global (Pessimistic):** Finds the absolute shortest distance between layers.
        3.  **Global (Optimistic):** Finds the longest, geologically valid thickness using advanced angular filtering.
    *   Ability to automatically read the dip angle from line attributes.

## Requirements

*   ArcGIS Pro version 3.6.0

## Installation

1.  Download the latest version of the `GMTB.pyt` file from the **[Releases](https://github.com/Kakucharz/GMTB/releases)** section.
2.  In ArcGIS Pro, in the `Catalog` panel, right-click the `Toolboxes` folder and select `Add Toolbox`.
3.  Browse to the downloaded `GMTB.pyt` file.

## License

This project is licensed under the **Creative Commons BY-NC-SA 4.0** license. For more information, see the [LICENSE](LICENSE) file.

---

# GMTB – Geological Mapping ToolBox

**Autor:** Karolina Kucharz
**Wersja:** 1.1.0

Zestaw narzędzi (Python Toolbox) dla środowiska ArcGIS Pro, przeznaczony do automatyzacji kluczowych zadań z zakresu cyfrowej kartografii geologicznej. 
Projekt został zrealizowany w ramach pracy dyplomowej na Wydziale Geologii, Geofizyki i Ochrony Środowiska Akademii Górniczo-Hutniczej im. Stanisława Staszica w Krakowie.

## Opis

GMTB automatyzuje procesy, które standardowo wymagają wielu manualnych kroków, oferując zintegrowany i intuicyjny potok analityczny. Toolbox składa się z dwóch głównych, komplementarnych narzędzi.

### Kluczowe Funkcjonalności

*   **Narzędzie "Generuj Linie Intersekcyjne"**
    *   Modelowanie płaszczyzn geologicznych na podstawie danych wejściowych.
    *   Obsługa dwóch metod definiowania płaszczyzny:
        1.  **Metoda 1 Punktu z Orientacją:** Dla wizualizacji znanych pomiarów (Dip/Dir).
        2.  **Metoda 3 Punktów:** Dla obliczania nieznanej orientacji na podstawie punktów.
    *   Automatyczne generowanie wektorowej linii przecięcia płaszczyzny z Numerycznym Modelem Terenu (NMT).
    *   Tworzenie powierzchni geologicznej w formacie TIN.

*   **Narzędzie "Oblicz Miąższość"**
    *   Obliczanie miąższości pozornej i rzeczywistej na podstawie dwóch linii intersekcyjnych.
    *   Oferuje trzy tryby analityczne:
        1.  **Lokalny:** Precyzyjny pomiar w punkcie wskazanym przez użytkownika.
        2.  **Globalny (Pesymistyczny):** Znajduje absolutnie najkrótszą odległość między warstwami.
        3.  **Globalny (Optymistyczny):** Znajduje najdłuższą, poprawną geologicznie miąższość dzięki zaawansowanemu filtrowaniu kątowemu.
    *   Możliwość automatycznego odczytu kąta zapadania (Dip) z atrybutów linii.

## Wymagania

*   ArcGIS Pro w wersji 3.6.0

## Instalacja

1.  Pobierz najnowszą wersję pliku `GMTB.pyt` z sekcji **[Releases](https://github.com/Kakucharz/GMTB/releases)**.
2.  W ArcGIS Pro, w panelu `Catalog`, kliknij prawym przyciskiem myszy na folder `Toolboxes` i wybierz `Add Toolbox`.
3.  Wskaż pobrany plik `GMTB.pyt`.

## Licencja

Ten projekt jest udostępniany na mocy licencji **Creative Commons BY-NC-SA 4.0**. Więcej informacji znajdziesz w pliku [LICENSE](LICENSE).

---
