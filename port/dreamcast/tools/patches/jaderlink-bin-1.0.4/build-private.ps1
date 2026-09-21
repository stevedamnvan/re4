param([Parameter(Mandatory=$true)][string]$SourceRoot,[Parameter(Mandatory=$true)][string]$OutputDll)
$ErrorActionPreference='Stop'
$revision=git -C $SourceRoot rev-parse HEAD
if($revision -ne '638e9d5f63fb8322cfab0d48f4ffbb23f6e7bb68'){throw 'Unexpected upstream revision'}
if(Test-Path -LiteralPath $OutputDll){throw 'Refusing to overwrite existing compiler output'}
$main=Join-Path $SourceRoot 'RE4_GCWII_BIN_TOOL\SHARED_GCWII_BIN\MainAction.cs'
if(-not ([IO.File]::ReadAllText($main).Contains('out intermediaryStructure, idxbin.UseVertexColor, ref FarthestVertex);'))){throw 'Apply reviewed use-colors.patch first'}
$paths=Get-ChildItem -LiteralPath (Join-Path $SourceRoot 'RE4_GCWII_BIN_TOOL') -Filter *.cs -Recurse | Where-Object {$_.Name -ne 'AssemblyInfo.cs'} | Select-Object -ExpandProperty FullName
Add-Type -Path $paths -OutputAssembly $OutputDll -IgnoreWarnings
Get-FileHash -LiteralPath $OutputDll -Algorithm SHA256
# In a fresh PowerShell process: Add-Type -Path OUTPUT_DLL;
# [SHARED_GCWII_BIN.MainAction]::MainContinue([string[]]@('-bat',PRIVATE_OBJ_PATH))