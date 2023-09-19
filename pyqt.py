'''
Liten app som lar deg velge bilder og sette koordinater i EXIF dataene til bildene.
Utarbeidd av Jan Helge Aalbu, 2023
Med hjelp av Chat GPT-4
'''

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
import piexif
from fractions import Fraction
from datetime import datetime
import requests

def to_deg(value, loc):
    """Convert decimal coordinates into degrees, minutes and seconds tuple for EXIF"""
    if value < 0:
        loc_value = loc[0]
    else:
        loc_value = loc[1]

    abs_value = abs(value)
    deg = int(abs_value)
    t1 = abs_value - deg
    min = int(t1 * 60)
    t2 = t1 - min / 60
    sec = int(t2 * 3600)

    return ((deg, 1), (min, 1), (sec, 1)), loc_value

def get_z_value(lat, lon):
    url = f"https://ws.geonorge.no/hoydedata/v1/datakilder/dtm1/punkt?koordsys=4258&nord={lat}&ost={lon}&geojson=false"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)
        data = response.json()
        return data['punkter'][0]['z']
    except requests.RequestException as e:
        print(f"An error occurred while fetching the Z-value: {e}")
        return None


def float_to_dms(value):
    deg = int(value)
    temp_min = (value - deg) * 60
    minute = int(temp_min)
    sec = round((temp_min - minute) * 60, 5)
    print(Fraction(deg, 1), Fraction(minute, 1), Fraction(sec).limit_denominator(100000))
    return (Fraction(deg, 1), Fraction(minute, 1), Fraction(sec).limit_denominator(100000))

class MyWebEnginePage(QWebEnginePage):
    def __init__(self, mainWindow, parent=None):
        super(MyWebEnginePage, self).__init__(parent)
        self.mainWindow = mainWindow
    
    def javaScriptConsoleMessage(self, level, msg, line, sourceID):
        #print(f"JavaScript message: {msg}")  # Debugging line
        if "Point clicked:" in msg:
            try:
                _, coordinates = msg.split("Point clicked:", 1)
                coordinates = coordinates.strip()
                lat, lon = coordinates.split(' ')
                lat = lat.strip()
                lon = lon.strip()
                self.mainWindow.update_coordinates(lat, lon)  # Use the reference to call the method
            except Exception as e:
                print(f"An error occurred: {e}")


class MainWindow(QMainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()
        
        self.browser = QWebEngineView()
        self.page = MyWebEnginePage(self, self.browser)  # Pass the reference to MainWindow
        self.browser.setPage(self.page)
        self.resize(850, 800)
        self.setWindowTitle('Bilder geotag')
        self.browser.setHtml('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Simple Leaflet Map</title>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
            </head>
            <body>
                <div id="map" style="width: 800px; height: 500px;"></div>
                <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
                <script>
                    var map = L.map('map').setView([61, 7], 7);
                    var marker;
                    
                    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                        maxZoom: 19,
                    }).addTo(map);
                    var states = L.tileLayer.wms('https://opencache.statkart.no/gatekeeper/gk/gk.open_gmaps?layers=topo4&zoom={z}&x={x}&y={y}',
                    {
                        format: 'image/png',
                        transparent: true,
                        layers: "topo4"
                    });
                    states.addTo(map);         

                    map.on('click', function(e) {
                        var lat = e.latlng.lat;
                        var lon = e.latlng.lng;

                        // Remove existing marker if any
                        if (marker) {
                            map.removeLayer(marker);
                        }

                        // Add a new marker
                        marker = L.marker([lat, lon]).addTo(map);

                        console.log('Point clicked:', lat, lon);
                    });
                </script>
            </body>
            </html>
        ''')

        self.lat_label = QLabel('Breddegrad: Ikkje valt')
        self.lon_label = QLabel('Lengdegrad: Ikkje valt')
        self.z_label = QLabel('Høgde: Ikkje funne')
        
        self.select_files_btn = QPushButton('Velg bilder')
        self.select_files_btn.clicked.connect(self.select_files)
        
        self.selected_files_display = QTextEdit()
        self.selected_files_display.setReadOnly(True)

        self.write_exif_btn = QPushButton('Skriv koordinater til EXIF')
        self.write_exif_btn.clicked.connect(self.write_exif_data)
        self.write_exif_btn.setEnabled(False)  # Disable it initially

        self.set_date_btn = QPushButton('Sett dato')
        self.set_date_btn.clicked.connect(self.set_creation_date)
        self.set_date_btn.setEnabled(False)

        layout = QVBoxLayout()
        layout.addWidget(self.browser)
        layout.addWidget(self.lat_label)
        layout.addWidget(self.lon_label)
        layout.addWidget(self.z_label)
        layout.addWidget(self.select_files_btn)
        layout.addWidget(self.selected_files_display)
        layout.addWidget(self.write_exif_btn)
        layout.addWidget(self.set_date_btn)
        
        container = QWidget()
        container.setLayout(layout)
        
        self.setCentralWidget(container)
        
        self.show()

    def set_exif_date(self, file_name, date_str):
        exif_dict = piexif.load(file_name)
        
        if "Exif" not in exif_dict:
            exif_dict["Exif"] = {}
            
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_str
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, file_name)


    def set_creation_date(self):
        date_input, ok = QInputDialog.getText(self, 'Sett dato', 'Skriv inn datoen (YYYY:MM:DD HH:MM:SS):')
        
        if ok:
            try:
                # Validate the date input
                datetime.strptime(date_input, '%Y:%m:%d %H:%M:%S')
                
                for file_name in self.files_missing_date:
                    self.set_exif_date(file_name, date_input)
                
                QMessageBox.information(self, 'Suksess', 'Dato satt for valgte bilder.')
            except ValueError:
                QMessageBox.warning(self, 'Ugyldig dato', 'Formatet på den innskrevne datoen er ugyldig.')
                
    def update_coordinates(self, lat, lon):
        self.lat = float(lat)
        self.lon = float(lon)
        self.z = get_z_value(lat, lon)
        if self.z is None:
            self.z = 0
        self.lat_label.setText(f'Breddegrad: {lat}')
        self.lon_label.setText(f'Lengdegrad: {lon}')
        self.z_label.setText(f'Høgde: {self.z}')

    def select_files(self):
        options = QFileDialog.Options()
        file_names, _ = QFileDialog.getOpenFileNames(self, "Velg filer", "", "JPEG Files (*.jpg);;All Files (*)", options=options)
        
        if file_names:
            files_with_exif = []
            files_missing_exif = []
            files_missing_date = []
            
            for file_name in file_names:
                try:
                    exif_dict = piexif.load(file_name)
                    if exif_dict.get("GPS"):
                        files_with_exif.append(file_name)
                    else:
                        files_missing_exif.append(file_name)

                    # Check if CreateDate tag exists, it's in the ExifIFD
                    if not exif_dict.get('Exif', {}).get(piexif.ExifIFD.DateTimeOriginal):
                        files_missing_date.append(file_name)
                        
                except Exception as e:
                    print(f"Feil ved lesing av EXIF data for {file_name}: {e}")
                    files_missing_exif.append(file_name)

            # Show message box if some files have EXIF data
            if files_with_exif:
                with_exif_str = '\n'.join(files_with_exif)
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Question)
                msg.setText(f"Nokon filer har allerede koordinater i EXIF data. Vil du skrive over?\nFiler med koordinater:\n{with_exif_str}")
                msg.setWindowTitle("Skriv over EXIF Data?")
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                returnValue = msg.exec()
                if returnValue == QMessageBox.Yes:
                    self.selected_files = file_names
                else:
                    self.selected_files = files_missing_exif
            else:
                self.selected_files = files_missing_exif
                missing_exif_str = '\n'.join(files_missing_exif)
                QMessageBox.warning(self, 'Manglende EXIF-koordinater', f'Følgende bilder mangler EXIF-koordinater:\n{missing_exif_str}')


            if self.selected_files:
                self.selected_files_display.setText("\n".join(self.selected_files))
                self.write_exif_btn.setEnabled(True)
                
                # If files are missing the CreateDate tag, enable the set_date button
                if files_missing_date:
                    self.set_date_btn.setEnabled(True)
                    self.files_missing_date = files_missing_date  # Save these files for later use
                    missing_files_str = '\n'.join(files_missing_date)
                    QMessageBox.warning(self, 'Ugyldig dato', f'Følgende bilder mangler datomerking:\n{missing_files_str}\n\nDu kan legge til dato ved å trykke på "Sett dato"-knappen.')

                if not hasattr(self, 'lat') or not hasattr(self, 'lon'):
                    QMessageBox.warning(self, 'Koordinater er ikkje valg', 'Velg eit punkt i kartet.')
                    self.write_exif_btn.setEnabled(False)
            else:
                QMessageBox.warning(self, 'Ingen filer valgt', 'Du har ikkje valgt filer for å skrive EXIF data til.')



            
    def set_exif_location(self, file_name, lat, lng):
        """Adds GPS position as EXIF metadata"""
        exif_dict = piexif.load(file_name)

        lat_deg = to_deg(lat, ["S", "N"])
        lng_deg = to_deg(lng, ["W", "E"])

        gps_ifd = {
            piexif.GPSIFD.GPSVersionID: (2, 0, 0, 0),
            piexif.GPSIFD.GPSAltitudeRef: 0,
            piexif.GPSIFD.GPSAltitude: (int(round(self.z) * 100), 100),
            piexif.GPSIFD.GPSLatitude: lat_deg[0],
            piexif.GPSIFD.GPSLatitudeRef: lat_deg[1],
            piexif.GPSIFD.GPSLongitude: lng_deg[0],
            piexif.GPSIFD.GPSLongitudeRef: lng_deg[1]
        }
        
        exif_dict["GPS"] = gps_ifd

        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, file_name)
        
    def write_exif_data(self):
        if hasattr(self, 'selected_files') and hasattr(self, 'lat') and hasattr(self, 'lon'):
            for file_name in self.selected_files:
                self.set_exif_location(file_name, self.lat, self.lon)
                
            QMessageBox.information(self, 'Suksess', 'Bildene har fått koordinater i EXIF.')
            
app = QApplication([])
window = MainWindow()
app.exec_()
