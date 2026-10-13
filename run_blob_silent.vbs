Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strScriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strScriptPath
' Launch blob.py windowless without any black command prompt window
WshShell.Run "pythonw.exe """ & strScriptPath & "\blob.py""", 0, False
Set WshShell = Nothing
Set fso = Nothing
