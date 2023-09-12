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

        self.lat_label = QLabel('Latitude: Not selected')
        self.lon_label = QLabel('Longitude: Not selected')
        
        self.select_files_btn = QPushButton('Select Images')
        self.select_files_btn.clicked.connect(self.select_files)
        
        self.selected_files_display = QTextEdit()
        self.selected_files_display.setReadOnly(True)

        self.write_exif_btn = QPushButton('Write EXIF Data')
        self.write_exif_btn.clicked.connect(self.write_exif_data)
        self.write_exif_btn.setEnabled(False)  # Disable it initially

        layout = QVBoxLayout()
        layout.addWidget(self.browser)
        layout.addWidget(self.lat_label)
        layout.addWidget(self.lon_label)
        layout.addWidget(self.select_files_btn)
        layout.addWidget(self.selected_files_display)
        layout.addWidget(self.write_exif_btn)
        
        container = QWidget()
        container.setLayout(layout)
        
        self.setCentralWidget(container)
        
        self.show()

    def update_coordinates(self, lat, lon):
        self.lat = float(lat)
        self.lon = float(lon)
        self.lat_label.setText(f'Latitude: {lat}')
        self.lon_label.setText(f'Longitude: {lon}')

    def select_files(self):
        options = QFileDialog.Options()
        file_names, _ = QFileDialog.getOpenFileNames(self,"Select Image Files", "","JPEG Files (*.jpg);;All Files (*)", options=options)
        
        if file_names:
            self.selected_files = file_names
            self.selected_files_display.setText("\n".join(file_names))
            self.write_exif_btn.setEnabled(True)  # Enable the button
            
            if not hasattr(self, 'lat') or not hasattr(self, 'lon'):
                QMessageBox.warning(self, 'Coordinates not set', 'Please select a point on the map first.')
                self.write_exif_btn.setEnabled(False)  # Disable the button

            
    def set_exif_location(self, file_name, lat, lng):
        """Adds GPS position as EXIF metadata"""
        exif_dict = piexif.load(file_name)

        lat_deg = to_deg(lat, ["S", "N"])
        lng_deg = to_deg(lng, ["W", "E"])

        gps_ifd = {
            piexif.GPSIFD.GPSVersionID: (2, 0, 0, 0),
            piexif.GPSIFD.GPSAltitudeRef: 0,
            piexif.GPSIFD.GPSAltitude: (10000, 1000),
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
                
            QMessageBox.information(self, 'Success', 'EXIF data written to selected images.')
            
app = QApplication([])
window = MainWindow()
app.exec_()
