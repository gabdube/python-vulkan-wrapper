# -*- coding: utf-8 -*-

from urllib.request import urlopen
from xml.etree import ElementTree
import re

INDENT = 4

# Map of used literal suffix to ctypes type
TYPES_SUFFIX = {'U': 'c_uint', 'ULL': 'c_uint64', 'f': 'c_float'}

# Used internally when resolving commands family names
HANDLE_NAMES = []

# Global properties used through the exportation
SHARED = {
    'xml_source': 'file',        # 'file' or 'web'
    'xml_path': 'vk.xml',        # If source is 'file': file path of the xml. If source is 'web': url to the xml
    'output_file_name': 'vk.py', # Output name

    # Values used internally
    'xml': None,
    'root': None,
    'output': None,
}

# map of "C" type to ctypes type
TYPES_MAP = {
    'void': 'None',
    'void*': 'c_void_p',
    'float': 'c_float',
    'uint8_t': 'c_uint8',
    'uint32_t': 'c_uint',
    'uint64_t': 'c_uint64',
    'int32_t': 'c_int',
    'size_t': 'c_size_t',
    'char': 'c_char',
    'char*': 'c_char_p',
}

### Templates START ###

# All spaces and empty lines are trimmed
# ` are replaced by ' '*INDENT
# ? are replaced by ''
# $ are replaced by '\n'

# Static stuff required for the library to work

IMPORTS_TEMPLATE = """
# -*- coding: utf-8 -*-
from ctypes import (c_void_p, c_float, c_uint8, c_uint, c_uint64, c_int, c_size_t, c_char, c_char_p, Structure, POINTER)
from platform import system
import sys
"""

INITIALIZATION_TEMPLATE = """
# Sysem initialization
system_name = system()
if system_name == 'Windows':
`from ctypes import WINFUNCTYPE, windll
`FUNCTYPE = WINFUNCTYPE
`vk = windll.LoadLibrary('vulkan-1')
elif system_name == 'Linux':
`from ctypes import CFUNCTYPE, cdll
`FUNCTYPE = CFUNCTYPE
`vk = cdll.LoadLibrary('libvulkan.so.1')
?
def MAKE_VERSION(major, minor, patch):
`return (major<<22) | (minor<<12) | patch
?
def define_structure(name, *args):
`return type(name, (Structure,), {'_fields_': args})
?
def load_functions(vk_object, functions_list, loader):
`functions = []
`for name, return_type, *args in functions_list:
``py_name = name.decode()[2::]
``fn_ptr = loader(vk_object, name)
``if fn_ptr is not None:
```fn = (FUNCTYPE(return_type, *args))(fn_ptr)
```functions.append((py_name, fn))
?
API_VERSION_1_0 = MAKE_VERSION(1,0,0)
"""

ARRAY_TEMPLATE = """({ARRAY_TYPE}*{ARRAY_LENGTH})"""

POINTER_TEMPLATE = """POINTER({POINTER_TYPE})"""

HANDLE_TEMPLATE = """{HANDLE_NAME} = {HANDLE_TYPE}$"""

FLAG_TEMPLATE = """{FLAG_NAME} = c_uint$"""

BASETYPE_TEMPLATE = """{BASETYPE_NAME} = {BASETYPE_TYPE}$"""

ENUM_LINE_TEMPLATE = """{ENUM_NAME} = {ENUM_VALUE}$"""
ENUM_TEMPLATE = """
{ENUM_NAME} = c_uint
{ENUM_LINES}
"""

STRUCTURE_ARGS_TEMPLATE = """`('{MEMBER_NAME}', {MEMBER_TYPE}),$"""
STRUCTURE_TEMPLATE = """
{STRUCT_NAME} = define_structure('{STRUCT_NAME}',${STRUCTURE_ARGS})$
"""

FUNCTIONS_PROTOTYPE_ARGS_TEMPLATE = """{PROTOTYPE_ARG_TYPE}, """
FUNCTIONS_PROTOTYPE_TEMPLATE = """{PROTOTYPE_NAME} = CFUNCTYPE( {PROTOTYPE_RETURN}, {PROTOTYPE_ARGS})$"""

COMMAND_ARGS_TEMPLATE = """{COMMAND_ARG_TYPE}, """
COMMAND_DEFINITION_TEMPLATE = """`(b'{COMMAND_NAME}', {COMMAND_RETURN}, {COMMAND_ARGS}),$"""
COMMAND_TEMPLATE = """{COMMAND_FAMILY_NAME}Functions = (${COMMAND_DEFINITIONS})$$"""

POST_INITIALIZATION_TEMPLATE = """
GetInstanceProcAddr = vk.vkGetInstanceProcAddr
GetInstanceProcAddr.restype = c_void_p
GetInstanceProcAddr.argtypes = (Instance, c_char_p)

print(local())

# Load the loader functions in the module namespace
for function_name, return_type, *args in LoaderFunctions:
`if function_name == 'vkGetInstanceProcAddr':
``continue

"""

### Templates END ###


### Utility functions START ###
def to_snake_case(name):
    "Transform the name of something to snake_case"
    def lower(m):
        g0 = m.group(0)
        g1, g2 = m.groups()
        
        if g1:
            return g0[0] + '_'+g1.lower() + g0[2]
        elif g2:
            return g0[0] + '_' + g0[1:3]
            
    name = re.sub('[^A-Z]([A-Z])[^A-Z]|[^A-Z]([A-Z])', lower, name)
        
    return name
def lstrip_t(template):
    return "".join( (ln.lstrip() for ln in template.splitlines(True)) )

def expand(template):
    return template.replace('`', " "*INDENT).replace('?', '').replace('$', '\n')

def pythonize_value(value):
    value = value.strip('()')
    for suffix, type_ in TYPES_SUFFIX.items():
        if value.endswith(suffix):
            value = value[0:-len(suffix)]
            return type_+('({})'.format(value))

    return value

def pythonize_field_name(_name):
    name = to_snake_case(_name)

    # Remove useless pointer identifier in field name
    if name.startswith('p_'):
        name = name[2::]

    return name

def remove_prefix(name):
    prefixes = ('Vk', 'VK_', 'PFN_vk')
    for prefix in prefixes:
        if name.startswith(prefix):
            return name[len(prefix)::]

    return name

def first(iterator):
    return next(iter(iterator))
def second(iterator):
    it = iter(iterator)
    next(it)
    return next(it)
def map_ctypes(type_item):
    if isinstance(type_item, str):
        type_name = type_item
    else:
        tail = type_item.tail[0] # Will be * if type is a pointer
        type_name = (type_item.text+tail).strip()

    if type_name in TYPES_MAP.keys():
        py_type = TYPES_MAP[type_name]
    else:
        py_type = remove_prefix(type_name) # For vulkan struct types

    return py_type

def filter_types(filter):
    return (t for t in SHARED['root'].find('types') if t.get('category') == filter)
def format_array(_type, length):
    return ARRAY_TEMPLATE.format(ARRAY_TYPE=_type, ARRAY_LENGTH=length)
def format_pointer(_type):
    if _type == 'None':
        return TYPES_MAP['void*']
    return POINTER_TEMPLATE.format(POINTER_TYPE=_type)
### Utility functions STOP  ###

### Parsing functions START ###
def prepare_templates():
    from sys import modules
    main = modules['__main__']
    for name in dir(main):
        if name.endswith('TEMPLATE'):
            template_content = getattr(main, name)
            setattr(main, name, expand(lstrip_t(template_content)))


def load_xml():
    s = SHARED
    if s['xml_source'] == 'web':
        # 'https://raw.githubusercontent.com/KhronosGroup/Vulkan-Docs/1.0/src/spec/vk.xml'
        s['xml'] = urlopen(s['xml_path'])
    else:
        s['xml'] = open(s['xml_path'])

def begin_generation():
    s = SHARED
    s['output'] = open(s['output_file_name'], 'w')
    s['root'] = ElementTree.fromstring(s['xml'].read())

def add_imports():
    SHARED['output'].write(IMPORTS_TEMPLATE)

def add_initialization():
    SHARED['output'].write("\n\n"+INITIALIZATION_TEMPLATE+"\n")

def parse_handles():
    s = SHARED
    o = s['output']

    o.write('\n# HANDLES\n\n')

    for handle in filter_types('handle'):
        if handle.find('type').text == 'VK_DEFINE_HANDLE':
            handle_type = TYPES_MAP['size_t']
        else:
            handle_type = TYPES_MAP['uint64_t']

        handle_name = remove_prefix(first(handle.iter('name')).text)
        o.write(HANDLE_TEMPLATE.format(HANDLE_NAME=handle_name, HANDLE_TYPE=handle_type))
        HANDLE_NAMES.append(handle_name)

    o.write('\n')

def parse_basetypes():
    s = SHARED
    o = s['output']

    o.write('\n# BASETYPES\n\n')


    for basetype in filter_types('basetype'):
        basetype_type = map_ctypes(second(basetype.iter('type')))
        basetype_name = remove_prefix(first(basetype.iter('name')).text)

        o.write(BASETYPE_TEMPLATE.format(BASETYPE_NAME=basetype_name, BASETYPE_TYPE=basetype_type))

    o.write('\n')

def parse_flags():
    s = SHARED
    o = s['output']

    o.write('\n# FLAGS\n\n')

    for flag in filter_types('bitmask'):
        flag_name = remove_prefix(first(flag.iter('name')).text)
        o.write(FLAG_TEMPLATE.format(FLAG_NAME=flag_name))

    o.write('\n')

def parse_enums():
    s = SHARED
    o = s['output']

    value_or_bitpos = lambda x: x.get('value') or x.get('bitpos')

    o.write('# ENUMS\n\n')

    for enum in s['root'].iter('enums'):
        enum_name = remove_prefix(enum.get('name').replace(' ', '_'))

        enum_mems = ( ( enum_mem.get('name'), value_or_bitpos(enum_mem) ) for enum_mem in enum if enum_mem.tag == 'enum')
        enum_mems = ( ( remove_prefix(n), pythonize_value(v) ) for n, v in enum_mems)
        enum_mems = (ENUM_LINE_TEMPLATE.format(ENUM_NAME=n, ENUM_VALUE=v) for n, v in enum_mems)
        enum_mems = ''.join(enum_mems)

        o.write( ENUM_TEMPLATE.format(ENUM_NAME=enum_name, ENUM_LINES=enum_mems) )

def parse_structure_member(struct_mem):
    type_node = first(struct_mem.iter('type'))
    name_node = first(struct_mem.iter('name'))
    mem_type = map_ctypes(type_node.text)
    mem_name = pythonize_field_name(name_node.text)

    # Check if type is a pointer
    if type_node.tail is not None and type_node.tail[0] == '*':
        mem_type = format_pointer(mem_type)

    # Check if type is an array
    if struct_mem.find('enum') is not None or ( (name_node.tail or ' ')[0] == '[' ):
        array_length = struct_mem.find('enum')
        if array_length is None:
            # Array length is a literal
            array_length = name_node.tail.replace('[', '').replace(']', '')
        else:
            # Array length is an enum
            array_length = remove_prefix(array_length.text)
        mem_type = format_array(mem_type, array_length)

    return (mem_name, mem_type)

def parse_structures():
    s = SHARED
    o = s['output']
    
    o.write('\n# STRUCTURES\n\n')

    for struct in filter_types('struct'):
        struct_name = remove_prefix(struct.get('name'))

        struct_mems = ( parse_structure_member(struct_mem) for struct_mem in struct.iter('member') )
        struct_mems = (STRUCTURE_ARGS_TEMPLATE.format(MEMBER_NAME=n, MEMBER_TYPE=t) for n, t in struct_mems)
        struct_mems = ''.join(struct_mems)

        o.write( STRUCTURE_TEMPLATE.format(STRUCT_NAME=struct_name, STRUCTURE_ARGS=struct_mems) )

def parse_funcpointers():
    s = SHARED
    o = s['output']

    def extract_return_type(text):
        clean_text = text.replace('typedef', '').replace('(VKAPI_PTR *', '').strip()
        return map_ctypes(clean_text)

    o.write('\n# FUNC POINTERS\n\n')

    for ptr in filter_types('funcpointer'):
        name = remove_prefix(first(ptr.iter('name')).text)
        
        ptrs_args_types = iter(ptr.iter('type'))
        return_v = extract_return_type(next(ptrs_args_types).text)

        ptrs_args_types = (map_ctypes(t) for t in ptrs_args_types)
        ptrs_args_types = (FUNCTIONS_PROTOTYPE_ARGS_TEMPLATE.format(PROTOTYPE_ARG_TYPE=t) for t in ptrs_args_types)
        ptrs_args_types = "".join(ptrs_args_types)

        o.write(FUNCTIONS_PROTOTYPE_TEMPLATE.format(PROTOTYPE_NAME=name, PROTOTYPE_ARGS=ptrs_args_types, PROTOTYPE_RETURN=return_v))

    o.write('\n')

def parse_command_argument_type(argtype):
    cmd_arg_type = map_ctypes(argtype.text)
    if argtype.tail is not None and argtype.tail[0] == "*":
        cmd_arg_type = format_pointer(cmd_arg_type)
    return COMMAND_ARGS_TEMPLATE.format(COMMAND_ARG_TYPE=cmd_arg_type)

def parse_commands():
    s = SHARED
    o = s['output']

    o.write('\n# FUNCTIONS \n\n')

    commands_groups = {}
    commands = s['root'].find('commands')
    for command in commands:
        command_type, command_name = command.find('proto')[::]
        command_type = map_ctypes(command_type.text)
        command_name = command_name.text

        _command_params = [ p.find('type') for p in command.iter('param') if p.find('type') is not None]
        command_params = (parse_command_argument_type(p) for p in _command_params)
        command_params = ''.join(command_params)
        
        # Commands are regrouped in "families". The family name being the first argument of the command
        # Functions that do not belong to a family (ex: VkCreateInstance) are assigned to the 'loader' family
        cmd = COMMAND_DEFINITION_TEMPLATE.format(COMMAND_NAME=command_name, COMMAND_RETURN=command_type, COMMAND_ARGS=command_params)
        group_key = map_ctypes(_command_params[0].text)
        if not group_key in HANDLE_NAMES or command_name == 'vkGetInstanceProcAddr':
            group_key = "Loader"
        
        if group_key not in commands_groups.keys():
            commands_groups[group_key] = [cmd]
        else:
            commands_groups[group_key].append(cmd)

    for cmd_family, cmds in commands_groups.items():
        cmds = ''.join(cmds)
        o.write(COMMAND_TEMPLATE.format(COMMAND_FAMILY_NAME=cmd_family, COMMAND_DEFINITIONS=cmds))
        

def add_post_initialization():
    SHARED['output'].write("\n\n"+POST_INITIALIZATION_TEMPLATE+"\n")
def end_generation():
    s = SHARED
    s['output'].close()
    s['xml'].close()

def export():
    prepare_templates()
    load_xml()
    begin_generation()
    add_imports()
    add_initialization()
    parse_basetypes()
    parse_handles()
    parse_flags()
    parse_enums()
    parse_structures()
    parse_funcpointers()
    parse_commands()
    add_post_initialization()
    end_generation()

### Parsing functions STOP  ###

if __name__ == '__main__':
    export()