#!powershell

#Requires -Module Ansible.ModuleUtils.Legacy
#AnsibleRequires -CSharpUtil Ansible.Basic

function Export-SecPol {
    param (
        [string]$CfgPath
    )

    secedit /export /cfg $CfgPath | Out-Null
}

function Get-PolicyValue {
    param (
        [string]$CfgPath,
        [string]$Key
    )

    $res = Select-String -Path "$CfgPath" -Pattern "^$Key"
    
    if ($res.Line -match "$Key\s*=\s*(.+)") {
        return $matches[1]
    }
    
    return $null
}

try {
    $spec = @{
        options = @{
            key = @{ type = "str" }
        }
        supports_check_mode = $true
    }

    $module = [Ansible.Basic.AnsibleModule]::Create($args, $spec)

    $key = $module.Params.key

    $TempPath = [System.IO.Path]::GetTempPath()
    $CfgPath = Join-Path $TempPath "secpol.cfg"

    Export-SecPol -CfgPath $CfgPath

    $Value = Get-PolicyValue -CfgPath $CfgPath -Key $key

    $result = if ($null -ne $Value) {
        $intValue = $Value -as [int]
        @{
            changed = $true
            value   = if ($null -eq $intValue) { $Value } else { [int]$intValue }
        }
    } else {
        @{
            changed = $false
            msg     = "Key $key not found"
        }
    }    
} catch {
    $result = @{
        failed = $true
        msg    = $_.Exception.Message
    }
}

$result | ConvertTo-Json -Compress
