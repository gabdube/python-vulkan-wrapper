import re
import urllib.request as req

src = req.urlopen("https://raw.githubusercontent.com/KhronosGroup/Vulkan-Docs/1.0/src/vulkan/vulkan.h").read().decode('utf-8')

BASE = r"""
#
# Vulkan wrapper generated from "https://raw.githubusercontent.com/KhronosGroup/Vulkan-Docs/1.0/src/vulkan/vulkan.h"
#

from ctypes import c_int8, c_uint16, c_int32, c_uint32, c_uint64, c_size_t, c_float, c_char, c_char_p, c_void_p, POINTER, Structure, Union, cast
from platform import system

# Helper functions
repr_fn = lambda self: str(dict(self._fields_))

def MAKE_VERSION(major, minor, patch):
    return (major<<22) | (minor<<12) | patch

def define_struct(name, *args):
    return type(name, (Structure,), {'_fields_': args, '__repr__': repr_fn})

def define_union(name, *args):
    return type(name, (Union,), {'_fields_': args, '__repr__': repr_fn})

def load_functions(vk_object, functions_list, loader):
    functions = []
    for name, prototype in functions_list:
        py_name = name.decode()[2::]
        fn_ptr = loader(vk_object, name)
        fn_ptr = cast(fn_ptr, c_void_p)
        if fn_ptr:
            fn = prototype(fn_ptr.value)
            functions.append((py_name, fn))
        elif __debug__ == True:
            print('Function {} could not be loaded. (__debug__ == True)'.format(py_name))
    return functions

API_VERSION_1_0 = MAKE_VERSION(1,0,0)

# System initialization
system_name = system()
if system_name == 'Windows':
    from ctypes import WINFUNCTYPE, windll
    FUNCTYPE = WINFUNCTYPE
    vk = windll.LoadLibrary('vulkan-1')
elif system_name == 'Linux':
    from ctypes import CFUNCTYPE, cdll
    FUNCTYPE = CFUNCTYPE
    vk = cdll.LoadLibrary('libvulkan.so.1')

# System types
HINSTANCE = c_size_t
HWND = c_size_t
HANDLE = c_size_t
DWORD = c_uint32
BOOL = c_uint32
LPCWSTR = POINTER(c_uint16)
xcb_connection_t = c_size_t
xcb_window_t = c_uint32
xcb_visualid_t = c_uint32
MirConnection = c_size_t
MirSurface = c_size_t
wl_display = c_void_p
wl_surface = c_void_p
Display = c_size_t
Window = c_uint32
VisualID = c_uint32
ANativeWindow = c_size_t
RROutput = c_uint32

SECURITY_ATTRIBUTES = define_struct('SECURITY_ATTRIBUTES', 
    ('nLength', c_uint32),
    ('lpSecurityDescriptor', c_void_p),
    ('bInheritHandle', c_uint32),
)

# Base types
Flags = c_uint32
Bool32 = c_uint32
DeviceSize = c_uint64
SampleMask = c_uint32

# Base constants
LOD_CLAMP_NONE = 1000.0
REMAINING_MIP_LEVELS = c_uint32(-1)
REMAINING_ARRAY_LAYERS = c_uint32(-1)
WHOLE_SIZE = c_uint64(-1)
ATTACHMENT_UNUSED = c_uint32(-1)
TRUE = 1
FALSE = 0
QUEUE_FAMILY_IGNORED = c_uint32(-1)
SUBPASS_EXTERNAL = c_uint32(-1)
MAX_PHYSICAL_DEVICE_NAME_SIZE = 256
UUID_SIZE = 16
MAX_MEMORY_TYPES = 32
MAX_MEMORY_HEAPS = 16
MAX_EXTENSION_NAME_SIZE = 256
MAX_DESCRIPTION_SIZE = 256
MAX_DEVICE_GROUP_SIZE_KHX = 32
LUID_SIZE_KHX = 8
LUID_SIZE_KHR = 8


"""[1:]

def no_vk(t):
    t = t.replace('Vk', '')
    t = t.replace('PFN_vk', 'Fn')
    t = t.replace('VK_', '')
    return t

def translate_type(t):
    table = { 
        "float": 'c_float',
        "uint32_t": 'c_uint32', 
        "uint64_t": 'c_uint64',
        "size_t": 'c_size_t',
        "float": 'c_float',
        'int32_t': 'c_int32',
        'int': 'c_int32',
        'uint8_t': 'c_int8',
        "char": "c_char",
        "void": "None", 
        "void*": "c_void_p", 
        "const void*": 'c_void_p',
        "const char*": 'c_char_p',
        "const char* const*": 'POINTER(c_char_p)',
        "struct wl_display*": "POINTER(wl_display)",
        "struct wl_surface*": "POINTER(wl_surface)",
        "const ObjectTableEntryNVX* const*": "POINTER(POINTER(ObjectTableEntryNVX))",
        'v': ''
     }
     
    if t in table.keys():
        return table[t]

    if t.endswith("*"):
        if t.startswith("const"):
            ttype = t[6:len(t)-1]
            ttype = table[ttype] if ttype in table else ttype
            return "POINTER({})".format(ttype)
        else:
            ttype = t[:len(t)-1]
            ttype = table[ttype] if ttype in table else ttype
            return "POINTER({})".format(ttype)
    
    return t

def parse_array(n, t):
    name, length = n.split('[')
    length = no_vk(length[0:len(length)-1])
    type_ = "{} * {}".format(do_type(t), length)
    return name, type_

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

def fix_arg(arg):
    name = to_snake_case(arg)

    # Remove useless pointer identifier in field name
    for p in ('s_', 'p_', 'pp_', 'pfn_'):
        if name.startswith(p):
            name = name[len(p)::]

    return name

def do_type(t):
    return translate_type(no_vk(t))

def parse_handles_def(f):
    f.write("# Handles types\n")
    handles = re.findall("VK_DEFINE_HANDLE\(Vk(\w+)\)", src, re.S)
    for h in handles:
        f.write("{} = c_size_t\n".format(h))

    handles_non_dispatchable = re.findall("VK_DEFINE_NON_DISPATCHABLE_HANDLE\(Vk(\w+)\)", src, re.S)
    for h in handles_non_dispatchable:
        f.write("{} = c_size_t\n".format(h))

def parse_flags_def(f):
    f.write("# Flags types\n")
    data = re.findall("typedef VkFlags Vk(\w+?);", src)
    
    for name in data:
        f.write("{} = Flags\n".format(name))

def parse_enums(f):
    f.write("# Enums\n")

    data = re.findall("typedef enum Vk(\w+) {(.+?)} \w+;", src, re.S)

    for name, fields in data:
        f.write("{} = c_uint32\n".format(name))
        for name, value in re.findall("VK_(\w+?) = (.*?)(?:,|})", fields, re.S):
                f.write("{} = {}\n".format(name, no_vk(value)))
        f.write("\n")

def parse_allocation_callback(f):
    # Allocation callback must be defined before the structs, but there are no good way to differenciate them
    # from the function pointers. Hence why they are hardcoded here
    f.write("""
# Allocation callback
FnAllocationFunction = FUNCTYPE(c_void_p, c_void_p, c_size_t, c_size_t, SystemAllocationScope)
FnReallocationFunction = FUNCTYPE(c_void_p, c_void_p, c_size_t, c_size_t, SystemAllocationScope)
FnFreeFunction = FUNCTYPE(None, c_void_p, c_void_p)
FnInternalAllocationNotification = FUNCTYPE(None, c_void_p, c_size_t, InternalAllocationType, SystemAllocationScope)
FnInternalFreeNotification = FUNCTYPE(None, c_void_p, c_size_t, InternalAllocationType, SystemAllocationScope)
FnDebugReportCallbackEXT = FUNCTYPE(Bool32, DebugReportFlagsEXT, DebugReportObjectTypeEXT, c_uint64, c_size_t, c_uint32, c_char_p, c_char_p, c_void_p)
"""[1::])

def parse_structs(f):
    data = re.findall("typedef (struct|union) Vk(\w+?) {(.+?)} \w+?;", src, re.S)

    for _type, name, fields in data:
        fields = re.findall("\s+(.+?)\s+([_a-zA-Z0-9[\]]+);", fields)
        f.write("{0} = define_{1}('{0}', \n".format(name, _type))
        for type_, name in fields:
            if '[' in name:
                name, type_ = parse_array(name, type_)
            f.write("    ('{}', {}),\n".format(fix_arg(name), do_type(type_)))
        f.write(")\n\n")

def parse_functions(f):
    data = re.findall("typedef (\w+\*?) \(\w+ \*(\w+)\)\((.+?)\);", src, re.S)

    for rt, name, fields in data:
        data_fields = ', '.join([do_type(t) for t in re.findall("(?:\s*|)(.+?)\s*\w+(?:,|$)", fields)])
        f.write("{} = FUNCTYPE({}, {})\n".format(no_vk(name), do_type(rt), data_fields))

def group_functions(f):
    data = re.findall("typedef (\w+\*?) \(\w+ \*(\w+)\)\((.+?)\);", src, re.S)
    group_map = {"Instance":[], "Device":[], "Loader":[]}

    for rt, vkname, fields in data:
        fields_types_name = [do_type(t) for t in re.findall("(?:\s*|)(.+?)\s*\w+(?:,|$)", fields)]
        table_name = fields_types_name[0]
        name = no_vk(vkname)

        if table_name in ('Device', 'Queue', 'CommandBuffer') and name != 'FnGetDeviceProcAddr':
            group_map["Device"].append(name)
        elif table_name in ('Instance', 'PhysicalDevice') or name == 'FnGetDeviceProcAddr':
            group_map["Instance"].append(name)
        elif table_name in ('c_void_p', '', 'DebugReportFlagsEXT') or name == 'FnGetInstanceProcAddr':
            # Skip the allocation function and the dll entry point
            pass
        else:
            #print(table_name, name)
            group_map["Loader"].append(name)

    for group_name, group_lines in group_map.items():
        f.write("{}Functions = (\n".format(group_name))
        for name in group_lines:
            f.write('  (b"{}", {}),\n'.format(name.replace('Fn', 'vk'), name))
        f.write(")\n\n")

def write_base_loader(f):
    f.write('''
# Loading proc
GetInstanceProcAddr = FnGetInstanceProcAddr((b"vkGetInstanceProcAddr", vk))

# Load the loader functions in the module namespace
loc = locals()
for name, fnptr in load_functions(Instance(0), LoaderFunctions, GetInstanceProcAddr):
    loc[name] = fnptr
del loc'''[1::])

with open("vk.py", 'w') as f:
    f.write(BASE)
    parse_handles_def(f)
    f.write("\n\n")
    parse_flags_def(f)
    f.write("\n\n")
    parse_enums(f)
    f.write("\n\n")
    parse_allocation_callback(f)
    f.write("\n\n")
    parse_structs(f)
    f.write("\n\n")
    parse_functions(f)
    f.write("\n\n")
    group_functions(f)
    f.write("\n\n")
    write_base_loader(f)
