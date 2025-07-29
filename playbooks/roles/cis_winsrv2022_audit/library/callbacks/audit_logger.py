DOCUMENTATION = '''
callback: audit_logger
type: notification
short_description: Custom logging callback
options:
  log_directory:
    description: 
      - Directory to store logs
    required: True
    ini:
      - section: callback_audit_logger
        key: log_directory

  output_format:
    description: 
      - List of file format to output to: markdown, json
    required: True
    ini:
      - section: callback_audit_logger
        key: output_format
'''

from ansible.plugins.callback import CallbackBase
from datetime import datetime, timezone
import os
import re
import json

class CallbackModule(CallbackBase):
  CALLBACK_VERSION = 2.0
  CALLBACK_TYPE = 'notification'
  CALLBACK_NAME = 'audit_logger'
  CALLBACK_NEEDS_WHITELIST = True

  # make sure log directory exists on start
  def v2_playbook_on_start(self, _):
    self.log_dir = self.get_option('log_directory') or './logs'
    os.makedirs(self.log_dir, exist_ok=True)

    output_format_raw = self.get_option('output_format') or "markdown,json"

    if isinstance(output_format_raw, str):
      self.output_format = [fmt.strip() for fmt in output_format_raw.split(',')]
    else:
      self.output_format = [output_format_raw]

    utc_now = datetime.now(timezone.utc)
    self.timestamp = utc_now.strftime('%Y%m%d_%H%M%S')
    self.formatted_date_time = utc_now.strftime("%A, %B %d, %Y %I:%M:%S %p")
    
    self.initialized_hosts = set()

  def v2_runner_on_ok(self, result):
    tags = result._task.tags

    # return early if tasks is not tagged to be logged
    if 'log_compliance' not in tags and 'log_script' not in tags: 
      return

    hostname = result._host.get_name()
    ip = result._host.vars.get('ansible_host', )
    host_id = f"{hostname}_{ip}"
    log_folder_name = f"{hostname}_{self.timestamp}"
    log_folder = os.path.join(self.log_dir, log_folder_name)
    
    # check if the host has already been initialized, ie. the log files exists and initial data has already been entered.
    # if not initialized, initialize the host, else continue
    if host_id not in self.initialized_hosts:
      os.makedirs(log_folder, exist_ok=True)

      if 'markdown' in self.output_format:
        self.md_logger = MDLogger(hostname, self.formatted_date_time, log_folder)
      if 'json' in self.output_format:
        self.json_logger = JSONLogger(hostname, self.formatted_date_time, log_folder)

      self.initialized_hosts.add(host_id) 

    section_number = result._result.get('ansible_facts', {}).get('section_number')

    if 'log_compliance' in tags:
      compliance_status = result._result.get('ansible_facts', {}).get('compliance_status')
      
      if 'markdown' in self.output_format:
        self.md_logger.log_compliance(section_number, compliance_status)
      if 'json' in self.output_format:
        self.json_logger.log_compliance(section_number, compliance_status)      

    if 'log_script' in tags:
      audit_output = result._result.get('ansible_facts', {}).get('audit_output')

      if 'FAIL' in audit_output.upper():
        if 'markdown' in self.output_format:
          self.md_logger.log_audit_script(section_number, audit_output)
        if 'json' in self.output_format:
          self.json_logger.log_audit_script(section_number, audit_output)    

class JSONLogger:
  def _writeToFile(self):
    with open(self.log_file, 'w') as file:
      json.dump(self.data, file, indent=2)

  def __init__(self, hostname, formatted_date_time, log_folder):
    self.hostname = hostname
    self.formatted_date_time = formatted_date_time
    self.log_file = os.path.join(log_folder, "audit_result.json")

    self.data = {
      "hostname": hostname,
      "timestamp": formatted_date_time,
      "compliance": {},
      "audit_failure_outputs": {}
    }
    
    self._writeToFile()
    
  def log_compliance(self, section_number, compliance_status):
    self.data["compliance"][section_number] = compliance_status
    self._writeToFile()
      
  def log_audit_script(self, section_number, audit_output):
    self.data["audit_failure_outputs"][section_number] = audit_output
    self._writeToFile()

class MDLogger:
  def __init__(self, hostname, formatted_date_time, log_folder):
    self.hostname = hostname
    self.formatted_date_time = formatted_date_time
    self.log_file = os.path.join(log_folder, "audit_result.md")

    content = f'''
# CIS Redhat Enterprise Linux 9 Audit Results

#### Hostname: {hostname}

#### Timestamp: {formatted_date_time}

| Recommendation # | Compliance Status |
| --- | --- |
## Count Summary
#### WIP

## Audit Failure Outputs 
    '''
    
    with open(self.log_file, 'w') as file:
      file.write(content)  

  def log_compliance(self, section_number, compliance_status):
    status_pattern = re.compile(r'^\|\s*\d+(\.\d+)*\s*\|\s*(Compliant|Not Compliant|Manual|Unknown|Warning)\s*\|$')
    separator_pattern = re.compile(r'^\|\s*---\s*\|\s*---\s*\|$')

    with open(self.log_file, 'r') as file:
      lines = file.readlines()

    separator_index= -1
    last_status_index = -1    

    for i, line in enumerate(lines):
      stripped = line.strip()
      if status_pattern.match(stripped):
        last_status_index = i
      elif separator_pattern.match(stripped):
        separator_index = i
    
    if last_status_index != -1:
      insert_index = last_status_index + 1
    elif separator_index != -1:
      insert_index = separator_index + 1
    else:
      insert_index = len(lines)

    lines.insert(insert_index, f"| {section_number} | {compliance_status} |" + '\n')

    with open(self.log_file, 'w') as file:
      file.writelines(lines)

  def log_audit_script(self, section_number, audit_output):
    with open(self.log_file, 'a') as file:
      file.write(f"\n### {section_number} \n```{ audit_output }\n```\n")