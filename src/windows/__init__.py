import windows.__resources_rc as resources_rc
from windows.about_window import AboutWindow
from windows.main_window import MainWindow
from windows.properties_window import PropertiesWindow

# To avoid circular references, do not import any of these classes directly
# Such as: 'from windows import AboutWindow'
# Instead do: 'import windows' and then reference `windows.AboutWindow` in your code!