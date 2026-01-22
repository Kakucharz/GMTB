# GMTB – Geological Mapping ToolBox

**Autor:** Karolina Kucharz
**Wersja:** 1.0.0

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
