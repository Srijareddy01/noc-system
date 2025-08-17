@echo off
echo Starting NOC Management System...
echo.
echo Installing dependencies...
pip install -r requirements.txt
echo.
echo Starting the application...
echo.
echo The application will be available at: http://localhost:5001
echo.
echo Press Ctrl+C to stop the server
python app.py
pause