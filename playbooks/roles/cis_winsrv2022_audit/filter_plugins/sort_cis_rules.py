import re

def extract_rule_key(filename):
    """
    Extracts a tuple of integers from filenames like 'win22cis_audit_rule_1_1_1.yml'
    for proper numeric sorting.
    """
    match = re.search(r'win22cis_audit_rule_(\d+(?:_\d+)*)', filename)
    if match:
        return tuple(int(part) for part in match.group(1).split('_'))
    return (0,)

def sort_cis_rules(file_list):
    return sorted(file_list, key=extract_rule_key)

class FilterModule(object):
    def filters(self):
        return {
            'sort_cis_rules': sort_cis_rules
        }
