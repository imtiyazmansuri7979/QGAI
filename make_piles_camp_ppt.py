import os

# Define the updated VBScript layout for Vadodara Institute of Piles
vbs_script_content = """
Dim pptApp, pptPres, newSlide, slideIndex
Set pptApp = CreateObject("PowerPoint.Application")
pptApp.Visible = True

' Create a standard widescreen 16:9 presentation layout
Set pptPres = pptApp.Presentations.Add
pptPres.PageSetup.SlideWidth = 720
pptPres.PageSetup.SlideHeight = 405

slideIndex = 1
Dim mapUrl, clinicName, clinicLocation
mapUrl = "https://goo.gl"
clinicName = "Vadodara Institute of Piles"
clinicLocation = "3rd Floor, Synergy Square, Near Waves Club, Vasna - Tandalja Rd, Tandalja, Vadodara, Gujarat 390012"

' Helper Subroutine to generate slides cleanly
Sub AddCampSlide(titleText, bodyText)
    Set newSlide = pptPres.Slides.Add(slideIndex, 12) ' 12 = ppLayoutBlank
    
    ' Add background color block
    Dim bgShape
    Set bgShape = newSlide.Shapes.AddShape(1, 0, 0, 720, 405)
    bgShape.Fill.Solid
    bgShape.Fill.ForeColor.RGB = RGB(240, 244, 248)
    bgShape.Line.Visible = 0
    
    ' Left accent boundary bar
    Dim accentBar
    Set accentBar = newSlide.Shapes.AddShape(1, 0, 0, 8, 405)
    accentBar.Fill.Solid
    accentBar.Fill.ForeColor.RGB = RGB(0, 86, 179)
    accentBar.Line.Visible = 0

    ' Slide Title Box
    Dim titleBox, tfTitle
    Set titleBox = newSlide.Shapes.AddTextbox(1, 40, 30, 640, 60)
    Set tfTitle = titleBox.TextFrame
    tfTitle.WordWrap = True
    tfTitle.TextRange.Text = titleText
    tfTitle.TextRange.Font.Size = 26
    tfTitle.TextRange.Font.Bold = True
    tfTitle.TextRange.Font.Name = "Arial"
    tfTitle.TextRange.Font.Color.RGB = RGB(0, 86, 179)

    ' Slide Content Box
    Dim bodyBox, tfBody
    Set bodyBox = newSlide.Shapes.AddTextbox(1, 40, 110, 640, 260)
    Set tfBody = bodyBox.TextFrame
    tfBody.WordWrap = True
    tfBody.TextRange.Text = bodyText
    tfBody.TextRange.Font.Size = 15
    tfBody.TextRange.Font.Name = "Arial"
    tfBody.TextRange.Font.Color.RGB = RGB(44, 62, 80)
    
    slideIndex = slideIndex + 1
End Sub

' --- SLIDE 1 ---
Set newSlide = pptPres.Slides.Add(slideIndex, 12)
Dim bgShape1
Set bgShape1 = newSlide.Shapes.AddShape(1, 0, 0, 720, 405)
bgShape1.Fill.Solid
bgShape1.Fill.ForeColor.RGB = RGB(240, 244, 248)
bgShape1.Line.Visible = 0

Dim tBox, tf1
Set tBox = newSlide.Shapes.AddTextbox(1, 50, 100, 620, 120)
Set tf1 = tBox.TextFrame
tf1.WordWrap = True
tf1.TextRange.Text = "Understanding the Hidden Link:" & vbCrLf & "How Your Drinking Water Affects Your Digestive Health"
tf1.TextRange.Font.Size = 28
tf1.TextRange.Font.Bold = True
tf1.TextRange.Font.Color.RGB = RGB(0, 86, 179)
tf1.TextRange.ParagraphFormat.Alignment = 2 ' Center

Dim subBox, tfSub
Set subBox = newSlide.Shapes.AddTextbox(1, 50, 240, 620, 80)
Set tfSub = subBox.TextFrame
tfSub.WordWrap = True
tfSub.TextRange.Text = "Free Medical Awareness Camp Presentation" & vbCrLf & "Brought to you by " & clinicName
tfSub.TextRange.Font.Size = 16
tfSub.TextRange.Font.Color.RGB = RGB(44, 62, 80)
tfSub.TextRange.ParagraphFormat.Alignment = 2
slideIndex = slideIndex + 1

' --- SLIDE 2 ---
AddCampSlide "Chronic Constipation: The Leading Cause of Piles", _
    "->  What are Piles? Swollen, permanently inflamed blood vessels inside or around your rectum and anus." & vbCrLf & vbCrLf & _
    "->  The Main Trigger: Heavy, forceful physical straining during bowel movements to pass hard stool packs." & vbCrLf & vbCrLf & _
    "->  The Role of Hydration: Your large intestine requires constant water intake to maintain soft stool consistency." & vbCrLf & vbCrLf & _
    "->  The Failure Cycle: Lack of fluid forces your body to suck water from waste, leaving it rocky and dry."

' --- SLIDE 3 ---
AddCampSlide "The 'Heavy Water' Trap: Why High TDS Lowers Your Thirst", _
    "->  Bitter and Metallic Taste: Heavy groundwater loaded with calcium and magnesium possesses an unappealing flavor." & vbCrLf & vbCrLf & _
    "->  Suppressed Thirst Response: Bad taste causes your brain to delay drinking. You only drink when parched." & vbCrLf & vbCrLf & _
    "->  False Fullness Sensation: Dense mineral water sits heavily in your stomach, falsely signaling that you are full." & vbCrLf & vbCrLf & _
    "->  Internal Water Drainage: Highly dense salt solutions draw fluid away from your bowel tract to process through kidneys."

' --- SLIDE 4 ---
AddCampSlide "Local Groundwater Hotspots in and around Vadodara", _
    "->  New Suburbs (TDS 1,200 - 2,500 ppm): Waghodia Road, Dabhoi Road belts, Bhayli, Vemali, and Gotri outskirts depend heavily on deep, unpalatable borewells." & vbCrLf & vbCrLf & _
    "->  Industrial Belts & Labor Hubs: Makarpura GIDC, Gorwa industrial limits, Ranoli, and Nandesari pull mineral-heavy aquifer water." & vbCrLf & vbCrLf & _
    "->  Severe Salinity Zones: Padra Taluka (Luna, Mobha, Ranu) has severe natural groundwater hardness that completely destroys stool quality."
    
' Add an interactive map click hyperlink to Slide 4
Dim mapBtn4
Set mapBtn4 = newSlide.Shapes.AddShape(1, 40, 345, 270, 30)
mapBtn4.Fill.Solid
mapBtn4.Fill.ForeColor.RGB = RGB(220, 53, 69)
mapBtn4.Line.Visible = 0
mapBtn4.TextFrame.TextRange.Text = "Click here to View Vadodara Piles Risk Map"
mapBtn4.TextFrame.TextRange.Font.Size = 11
mapBtn4.TextFrame.TextRange.Font.Bold = True
mapBtn4.TextFrame.TextRange.Font.Color.RGB = RGB(255, 255, 255)
newSlide.Hyperlinks.Add mapBtn4, mapUrl

' --- SLIDE 5 ---
AddCampSlide "Action Plan for Healthy Hydration & Gut Relief", _
    "->  Test Your Drinking Water: Ensure your final drinking water TDS rests comfortably between 50 to 150 ppm." & vbCrLf & vbCrLf & _
    "->  Check Purification Setup: Use an RO (Reverse Osmosis) unit equipped with a properly calibrated TDS controller. Standard UV filters cannot remove hardness." & vbCrLf & vbCrLf & _
    "->  Enforce a Fluid Target: Actively consume 2.5 to 3 Liters of lightweight water daily. Do not wait until your throat feels dry." & vbCrLf & vbCrLf & _
    "->  Monitor Your Body: Clear or light straw-color urine means safe. Dark yellow indicates a high risk for piles."

' --- SLIDE 6 ---
AddCampSlide "Advanced Medical Care at Vadodara Institute of Piles", _
    "->  Comprehensive Diagnosis: Professional diagnostic screens for Piles, Fissures, and complex Fistulas." & vbCrLf & vbCrLf & _
    "->  Modern Painless Laser Treatments: Advanced day-care laser procedures offering zero cutting, no painful dressings, and quick recovery." & vbCrLf & vbCrLf & _
    "->  Exclusive Camp Benefits Today: Free medical officer evaluation, free digital TDS water assessments (hand over your sample bottle!), and complementary diet tracking charts."

' --- SLIDE 7 ---
Set newSlide = pptPres.Slides.Add(slideIndex, 12)
Dim bgShape7
Set bgShape7 = newSlide.Shapes.AddShape(1, 0, 0, 720, 405)
bgShape7.Fill.Solid
bgShape7.Fill.ForeColor.RGB = RGB(240, 244, 248)
bgShape7.Line.Visible = 0

Dim cBox, tf7
Set cBox = newSlide.Shapes.AddShape(1, 40, 25, 640, 90)
cBox.Fill.Solid
cBox.Fill.ForeColor.RGB = RGB(0, 86, 179)
cBox.Line.Visible = 0
Set tf7 = cBox.TextFrame
tf7.TextRange.Text = "Take Control of Your Health Today!" & vbCrLf & "Open Question & Answer Session"
tf7.TextRange.Font.Size = 20
tf7.TextRange.Font.Bold = True
tf7.TextRange.Font.Color.RGB = RGB(255, 255, 255)
tf7.TextRange.ParagraphFormat.Alignment = 2

Dim infoBox, tfInfo
Set infoBox = newSlide.Shapes.AddTextbox(1, 40, 130, 640, 180)
Set tfInfo = infoBox.TextFrame
tfInfo.WordWrap = True
tfInfo.TextRange.Text = "Hospital Location: " & clinicLocation & vbCrLf & vbCrLf & _
                       "Booking / Emergency Helpline: [Insert Your Phone Number Here]" & vbCrLf & vbCrLf & _
                       "Next Step: Please proceed to the registration desk right outside for your free checkup appointment."
tfInfo.TextRange.Font.Size = 13
tfInfo.TextRange.Font.Color.RGB = RGB(44, 62, 80)

' Add a clear clinic location route button linking to Google Maps link on Slide 7
Dim mapBtn7
Set mapBtn7 = newSlide.Shapes.AddShape(1, 40, 335, 260, 35)
mapBtn7.Fill.Solid
mapBtn7.Fill.ForeColor.RGB = RGB(40, 167, 69)
mapBtn7.Line.Visible = 0
mapBtn7.TextFrame.TextRange.Text = "Click here to Get Clinic Directions on Map"
mapBtn7.TextFrame.TextRange.Font.Size = 12
mapBtn7.TextFrame.TextRange.Font.Bold = True
mapBtn7.TextFrame.TextRange.Font.Color.RGB = RGB(255, 255, 255)
newSlide.Hyperlinks.Add mapBtn7, mapUrl

' Save presentation cleanly to disk area
Dim currentDir
currentDir = "C:\\QGAI\\"
pptPres.SaveAs currentDir & "Piles_Clinic_Camp_Presentation.pptx"
"""

vbs_file_path = "C:\\QGAI\\generate_slides.vbs"

# Explicitly save with UTF-8 to handle script layouts properly
with open(vbs_file_path, "w", encoding="utf-8") as f:
    f.write(vbs_script_content)

try:
    import subprocess
    subprocess.run(["cscript.exe", vbs_file_path], check=True)
    print("Success! PowerPoint file generated perfectly for Vadodara Institute of Piles.")
except Exception as e:
    print(f"Notice: Execution complete. Check C:\\QGAI\\ directory. Details: {e}")

if os.path.exists(vbs_file_path):
    os.remove(vbs_file_path)
