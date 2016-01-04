#!/usr/bin/env python

# config_gen.py
#
# Generate .h files from given configuration


try:
    import yaml
except (ImportError, NotImplementedError):
    import os,sys
    sys.path.append("./ptlsim/lib/python")
    import yaml

try:
    from yaml import CLoader as Loader
except:
    from yaml import Loader

import os
import sys
from optparse import OptionParser, OptionGroup

_DEBUG = False

auto_gen_header = '''/*
 * DO NOT MODIFY
 * This file is atuomatically generated by Marss Builder.
 * If you want to make any changes to this configuration please make
 * changes to '.conf' file which was used to generate this.
 * 
 * conf file: %s
 */


'''

namespace_header = '''
namespce %s {

'''

namespace_footer = '''
}; // namespace %s
'''

machine_includes = '''
#include <globals.h>
#include <machine.h>
#include <basecore.h>
#include <memoryHierarchy.h>
#include <cpuController.h>

'''

machine_namespaces = '''
using namespace Core;
using namespace Memory;

'''

machine_func_start = '''
void gen_%s_machine(BaseMachine& machine)
{

'''

machine_func_end = '''
    machine.setup_interconnects();
    machine.memoryHierarchyPtr->setup_full_flags();
}

MachineBuilder %s("%s", &gen_%s_machine);
'''

machine_core_loop_start = '''
    while(!machine.context_used.allset()) {
'''

machine_loop_end = '''
    }

'''

machine_for_each_core_loop_i = '''
    foreach(i, machine.get_num_cores()) {
'''

machine_for_each_num_loop_i = '''
    foreach(i, %d) {
'''

machine_for_each_core_loop_j = '''
        foreach(j, machine.get_num_cores()) {
'''

machine_for_each_num_loop_j = '''
        foreach(j, %d) {
'''

machine_loop_end_j = '''
        }

'''

machine_core_create = '''
        CoreBuilder::add_new_core(machine, "%s", "%s");
        if (machine.context_used.allset()) break;
'''

machine_controller_create = '''
        ControllerBuilder::add_new_cont(machine, i, "%s", "%s", %s);
'''

machine_connection_def = '''
        ConnectionDef* connDef = machine.get_new_connection_def("%s",
                "%s", i);

'''

machine_add_connection = '''
        stringbuf %s;
        %s << "%s";
        machine.add_new_connection(connDef, %s.buf, %s);

'''

machine_add_connection_i = '''
        stringbuf %s;
        %s << "%s" << i;
        machine.add_new_connection(connDef, %s.buf, %s);

'''

machine_add_connection_j = '''
            stringbuf %s;
            %s << "%s" << j;
            machine.add_new_connection(connDef, %s.buf, %s);

'''

machine_option_add_i = '''
        machine.add_option("%s", i, "%s", %s);
'''

machine_core_option_add = '''
        machine.add_option("%s", machine.coreid_counter, "%s", %s);
'''

cache_typedef_cacheline = '''
typedef CacheLines<%s, %s, %s, %s> %sCacheLines;

'''

cache_case_stmt = '''
        case %s:
            return new %s(%s_READ_PORTS, %s_WRITE_PORTS);
'''

cache_line_func = '''
namespace Memory {
    struct CacheLinesBase;
    CacheLinesBase* get_cachelines(int type);
};
'''

core_cont_set_icache_bits = '''
        Controller** cont = machine.controller_hash.get(core_);
        assert(cont);
        CPUController* cpuCont = (CPUController*)((*cont));
        cpuCont->set_icacheLineBits(log2(%s));
'''

core_cont_set_dcache_bits = '''
        Controller** cont = machine.controller_hash.get(core_);
        assert(cont);
        CPUController* cpuCont = (CPUController*)((*cont));
        cpuCont->set_dcacheLineBits(log2(%s));
'''

handle_cpuid_fn_start = '''
int %s_handle_cpuid(uint32_t index, uint32_t count, uint32_t *eax, uint32_t *ebx,
        uint32_t *ecx, uint32_t *edx)
{

'''

set_handle_cpuid_fn_ptr = '''
    machine.handle_cpuid = &%s_handle_cpuid;

'''

# FIXME : Currently we set only 1 thread per core
handle_cpuid_core_info = '''
    uint32_t cores_info =
        (((0) << 14) & 0x3fc000) |
        (((NUMBER_OF_CORES - 1) << 26) & 0xfc00000);
'''

# Use following information to set registers in CPUID instruction
#
# Cache info from OS
# EAX : Bits		Info
#          4-0		0 = Null - no more cache
#                     1 = Data cache
#                     2 = Instruction cache
#                     3 = Unified cache
#                     4-31 = reserved
#          7-5		Cache Level (starts from 1)
#          8			Self initalizing cache
#          9			Fully Associative cache
#          25-14		Maximum number of IDs of logical
#                     Processors sharing this cache
#          31-26		Maximum number of cores in package
#
# EBX : Bits		Info
#       11-0		Coherency line size
#       21-12		Physical line partition
#       31-22		Ways of Associativity
#
# ECX : Number of Sets
# EDX : Bits		Info
#          0			Writeback/Invalid on sharing
#          1			Inclusive or not of lower caches
#
handle_cpuid_cache_switch = '''
    switch (index) {
        case 4:
            switch (count) {
                case 0: { // L1-D cache info
                            *eax = 0x121 | cores_info;
                            *ebx = ((%(L1D_LINE_SIZE)d & 0xfff) |
                                    ((%(L1D_LINE_SIZE)d << 12) & 0x3ff000) |
                                    ((%(L1D_WAY_COUNT)d << 22) & 0xffc00000) );
                            *ecx = %(L1D_SET_COUNT)d;
                            *edx = 0x1;
                            break;
                        }
                case 1: { // L1-I cache info
                            *eax = 0x122 | cores_info;
                            *ebx = ((%(L1I_LINE_SIZE)d & 0xfff) |
                                    ((%(L1I_LINE_SIZE)d << 12) & 0x3ff000) |
                                    ((%(L1I_WAY_COUNT)d << 22) & 0xffc00000) );
                            *ecx = %(L1I_SET_COUNT)d;
                            *edx = 0x1;
                            break;
                        }
                case 2: { // L2 cache info
                            uint32_t l2_core_info =
                                (((%(CORES_PER_L2)s) << 14) &
                                 0x3fc000);
                            l2_core_info |= ((NUMBER_OF_CORES - 1) << 26) &
                                0xfc00000;
                            *eax = 0x143 | l2_core_info;
                            *ebx = ((%(L2_LINE_SIZE)d & 0xfff) |
                                    ((%(L2_LINE_SIZE)d << 12) & 0x3ff000) |
                                    ((%(L2_WAY_COUNT)d << 22) & 0xffc00000) );
                            *ecx = %(L2_SET_COUNT)d;
                            *edx = 0x1;
                            break;
                        }
                %(l3_cache_info)s
                default: {
                             *eax = 0;
                             *ebx = 0;
                             *ecx = 0;
                             *edx = 0;
                         }
            }
            break;
        default:
            /* unsupported CPUID */
            return 0;
    }

    return 1;
}

'''

handle_cpuid_l3_cache_info = '''
                case 3: { // L3 cache info
                            uint32_t l3_core_info =
                                (((NUMBER_OF_CORES) << 14) &
                                 0x3fc000);
                            l3_core_info |= ((NUMBER_OF_CORES - 1) << 26) &
                                0xfc00000;
                            *eax = 0x163 | l3_core_info;
                            *ebx = ((%(L3_LINE_SIZE)d & 0xfff) |
                                    ((%(L3_LINE_SIZE)d << 12) & 0x3ff000) |
                                    ((%(L3_WAY_COUNT)d << 22) & 0xffc00000) );
                            *ecx = %(L3_SET_COUNT)d;
                            *edx = 0x1;
                            break;
                        }
'''

def _error(string, parser=None):
    string = "[ERROR] [CONFIG_GEN] %s" % (string)
    print(string)
    if parser:
        print("Parser: %s" % parser)
        print("%s" % parser.usage)
    sys.exit(-1)

def _debug(string):
    if _DEBUG:
        string = "[CONFIG_GEN] %s" % string
        print(string)

def get_arg_parser():
    parser = OptionParser()
    group = OptionGroup(parser, "Required flags")
    group.add_option("-c", "--config", action="store",
            type="string", dest="config_filename")
    group.add_option("-t", "--type", action="store",
            type="string", dest="type",
            help="Type of config file to generate: core, "
            "cache, machine")
    group.add_option("-o", "--output", action="store",
            type="string", dest="output")
    group.add_option("-n", "--name", action="store",
            type="string", dest="name")
    parser.add_option_group(group)
    parser.add_option("-d", "--debug", action="store_true",
            dest="debug", default=False)
    return parser

def check_options(options, parser):
    if not options.config_filename:
        parser.error("Please provide configuration file.")
    if not options.type or options.type not in ["core", "cache", "machine"]:
        parser.error("Please provide correct type : core, cache")
    if not options.output:
        parser.error("Please provide output file name.")
    if not options.name:
        parser.error("Please provide configuration object name.")
    # set _DEBUG if debug is set
    if options.debug:
        global _DEBUG
        _DEBUG = True

def read_config(config_filename):
    with open(config_filename, 'r') as config_file:
        return yaml.load(config_file)

def check_config(config, options):
    type_conf = config[options.type]
    if options.type != "cache" and not type_conf.has_key(options.name):
        _error("Invalid configuration name.")

def get_requested_type_config(config, config_type):
    return config[config_type]

def get_param_string(key, val):
    ret_str = "#define %s " % key
    if type(val) == str:
        ret_str += "\"%s\"" % val
    else:
        ret_str += "%s" % val
    return ret_str

def write_params_file(config, options):
    obj_conf = config[options.type][options.name]
    if obj_conf.has_key("params"):
        params = obj_conf["params"]
    else:
        params = {}

    with open(options.output, 'w') as out_file:
        out_file.write(auto_gen_header % obj_conf["_file"])
        out_file.write("/* Configuration Name: %s */\n\n" %
                options.name)
        for key,val in params.items():
            key = '%s_%s' % (obj_conf["base"], key)
            out_file.write("%s\n" % get_param_string(key.upper(), val))

        # Write core name
        out_file.write("#define %s_CORE_NAME \"%s\"\n" % (
            obj_conf["base"].upper(), options.name))

        out_file.write("#define %s_CORE_MODEL %s\n" % (
            obj_conf["base"].upper(), options.name))

def write_machine_headers(out_file):
    out_file.write(machine_includes)
    out_file.write(machine_namespaces)

def write_option_logic(st, of, name, opt, val):
    if type(val) == str:
        val = '"%s"' % val
    elif type(val) == bool:
        val = '%s' % str(val).lower()
    of.write(st % (name, opt, val))

def get_cache_cfg(config, name):
    for cache in config["caches"]:
        if cache["name_prefix"] == name:
            return cache
    return None

def write_core_logic(config, m_conf, of):
    of.write(machine_core_loop_start)
    for core in m_conf["cores"]:
        assert config["core"].has_key(core["type"]), \
                "Can't find core configuration %s" % core["type"]
        core_cfg = config["core"][core["type"]]

        if core.has_key("option"):
            for key,val in core["option"].items():
                write_option_logic(machine_core_option_add, of,
                        core["name_prefix"], key, val)

        of.write(machine_core_create % (core["name_prefix"],
            core["type"]))
    of.write(machine_loop_end)

def write_cont_logic(config, m_conf, of, n1, n2):
    for cache in m_conf[n1]:
        assert config[n2].has_key(cache["type"]), \
                "Can't find cache configuration %s" % \
                cache["type"]
        cache_cfg = config[n2][cache["type"]]
        name_pfx = cache["name_prefix"]
        base = cache_cfg["base"]
        if n2 == "memory":
            c_type = "0"
        else:
            c_type = cache["type"].upper()

        if cache["insts"] == "$NUMCORES":
            of.write(machine_for_each_core_loop_i)
        elif type(cache["insts"]) == int or cache["insts"].isdigit():
            of.write(machine_for_each_num_loop_i %
                    int(cache["insts"]))

        # Check if there are any options to add
        if cache.has_key("option"):
            for key,val in cache["option"].items():
                write_option_logic(machine_option_add_i, of, name_pfx,
                        key, val)

        of.write(machine_controller_create %
                (name_pfx, base, c_type))
        of.write(machine_loop_end)

def write_cache_cont_logic(config, m_conf, of):
    write_cont_logic(config, m_conf, of, "caches", "cache")

def write_mem_cont_logic(config, m_conf, of):
    write_cont_logic(config, m_conf, of, "memory", "memory")

def get_cache_line_size(config, m_conf, cache_name):
    for cache in m_conf["caches"]:
        if cache["name_prefix"] in cache_name:
            cfg = config["cache"][cache["type"]]
            l_size = cfg["params"]["LINE_SIZE"]
            return l_size

def write_interconn_logic(config, m_conf, of):
    for interconn in m_conf["interconnects"]:
        base = interconn["type"]
        count = 0

        for conn in interconn["connections"]:

            # First check if each controller's name end with $ or not
            all_cores = True
            for cont in conn.keys():
                if cont[-1] != '$':
                    all_cores = False
                else:
                    assert all_cores == True
                    if 'core' not in cont:
                        c_cfg = get_cache_cfg(m_conf, cont.rstrip('$'))
                        assert c_cfg, "Can't find cache for %s" % cont
                        assert c_cfg["insts"] == "$NUMCORES"

            all_conts = False
            for cont in conn.keys():
                if cont[-1] == '*':
                    all_conts = True
                    if 'core' not in cont:
                        c_cfg = get_cache_cfg(m_conf, cont.rstrip('*'))
                        assert c_cfg, "Can't find cache for %s" % cont
                        assert c_cfg["insts"] == "$NUMCORES"

            if all_cores:
                assert all_conts == False, \
                        "Connections can't have $ and * togather"

            if all_cores == True:
                cont_names = [key.rstrip('$') for key in conn.keys()]
                int_name = base + "_" + ''.join(cont_names)
                of.write(machine_for_each_core_loop_i)
                of.write(machine_connection_def % (base,
                    int_name))

                if interconn.has_key("option"):
                    for key,val in interconn["option"].items():
                        write_option_logic(machine_option_add_i, of, int_name,
                                key, val)

                # This variables are used to set CPU Controller's icache and
                # dcache line bits
                write_core_cache_bits = False
                core_cont_conn_type = ''

                for cont,conn_type in conn.items():
                    cont = cont.rstrip('$')
                    conn_type = 'INTERCONN_TYPE_%s' % conn_type
                    of.write(machine_add_connection_i % (cont,
                        cont, cont, cont, conn_type))
                    if 'core' in cont:
                        write_core_cache_bits = True
                        core_cont_conn_type = conn_type

                if write_core_cache_bits:
                    if core_cont_conn_type == 'INTERCONN_TYPE_I':
                        of.write(core_cont_set_icache_bits % (
                            get_cache_line_size(config, m_conf, cont)))
                    elif core_cont_conn_type == 'INTERCONN_TYPE_D':
                        of.write(core_cont_set_dcache_bits % (
                            get_cache_line_size(config, m_conf, cont)))

                of.write(machine_loop_end)

            elif all_conts == True:
                int_name = base + "_" + str(count)
                of.write(machine_for_each_num_loop_i % 1)
                of.write(machine_connection_def % (base,
                    int_name))

                if interconn.has_key("option"):
                    for key,val in interconn["option"].items():
                        write_option_logic(machine_option_add_i, of, int_name,
                                key, val)

                for cont, conn_type in conn.items():
                    conn_type = 'INTERCONN_TYPE_%s' % conn_type
                    if cont[-1] == '*':
                        cont = cont.rstrip('*')
                        of.write(machine_for_each_core_loop_j)
                        of.write(machine_add_connection_j % (cont,
                            cont, cont, cont, conn_type))
                        of.write(machine_loop_end_j)
                    else:
                        of.write(machine_add_connection % (cont,
                            cont, cont, cont, conn_type))

                of.write(machine_loop_end)
            else:
                int_name = base + "_" + '_'.join(conn.keys())
                of.write(machine_for_each_num_loop_i % 1)
                of.write(machine_connection_def % (base,
                    int_name))

                if interconn.has_key("option"):
                    for key,val in interconn["option"].items():
                        write_option_logic(machine_option_add_i, of, int_name,
                                key, val)

                for cont, conn_type in conn.items():
                    conn_type = 'INTERCONN_TYPE_%s' % conn_type
                    of.write(machine_add_connection % (cont,
                        cont, cont, cont, conn_type))

                of.write(machine_loop_end)

            count += 1

def fill_cache_info(cfg, cache_info, pfx):
    size = get_cache_size(cfg["params"]["SIZE"])
    assoc = cfg["params"]["ASSOC"]
    l_size = cfg["params"]["LINE_SIZE"]
    sets = (size / l_size) / assoc

    cache_info["%s_LINE_SIZE" % pfx] = l_size
    cache_info["%s_WAY_COUNT" % pfx] = assoc
    cache_info["%s_SET_COUNT" % pfx] = sets

def gen_handle_cpuid_fn(config, m_conf, m_name, of):

    # Find all levels of cahces from machine configuration
    cache_info = {}
    l3_present = False

    cache_info["l3_cache_info"] = ""

    for cache in m_conf["caches"]:
        cfg = config["cache"][cache["type"]]
        if "1" in cache["name_prefix"]:
            if "D" in cache["name_prefix"].upper():
                fill_cache_info(cfg, cache_info, "L1D")
            elif "I" in cache["name_prefix"].upper():
                fill_cache_info(cfg, cache_info, "L1I")
        elif "2" in cache["name_prefix"]:
            fill_cache_info(cfg, cache_info, "L2")
            if cache["insts"] == "$NUMCORES":
                cache_info["CORES_PER_L2"] = "1"
            else:
                num_l2_inst = int(cache["insts"])
                cache_info["CORES_PER_L2"] = "(NUMBER_OF_CORES)/%d" % (
                        num_l2_inst)
        elif "3" in cache["name_prefix"]:
            fill_cache_info(cfg, cache_info, "L3")
            cache_info["l3_cache_info"] = handle_cpuid_l3_cache_info

    # Now write the function
    of.write(handle_cpuid_fn_start % m_name)
    of.write(handle_cpuid_core_info)

    # We apply string formatting twice to get L3 cache info
    cache_switch = handle_cpuid_cache_switch % cache_info
    cache_switch = cache_switch % cache_info
    of.write(cache_switch)

def generate_machine(config, options):
    with open(options.output, 'w') as of:
        m_conf = config[options.type][options.name]
        of.write(auto_gen_header % m_conf["_file"])
        write_machine_headers(of)

        # Write cpuid handler function
        gen_handle_cpuid_fn(config, m_conf, options.name, of)

        # Write function start
        m_name = options.name
        of.write(machine_func_start % (m_name))

        # Write core creation
        write_core_logic(config, m_conf, of)

        # Write CPUControllers for each core
        of.write(machine_for_each_core_loop_i)
        of.write(machine_controller_create % ("core_", "cpu", "0"))
        of.write(machine_loop_end)

        # Write each cache controllers
        write_cache_cont_logic(config, m_conf, of)

        # Write memory controllers
        write_mem_cont_logic(config, m_conf, of)

        # Write interconnect and connection logic
        write_interconn_logic(config, m_conf, of)

        # Connect cpuid handler function
        of.write(set_handle_cpuid_fn_ptr % (m_name))

        # Write function end
        of.write(machine_func_end % (m_name, m_name, m_name))

def generate_cache_header(config, options):
    with open(options.output, 'w') as of:
        of.write(auto_gen_header % " ")
        of.write("enum {\n")
        for cache,cfg in config["cache"].items():
            of.write("\t%s,\n" % cache.upper())
        of.write("};\n")
        of.write(cache_line_func)

def get_cache_size(size):
    size = size.lower()
    multiplier = 1
    if size[-1] == 'm':
        multiplier = 1024*1024
    elif size[-1] == 'k':
        multiplier = 1024
    elif size[-1] == 'g':
        multiplier = 1024*1024*1024

    s1 = int(size[:-1])
    return s1 * multiplier

def generate_cache_logic(config, options):
    with open(options.output, 'w') as of:
        of.write(auto_gen_header % " ")
        of.write("\n#include <globals.h>\n")
        of.write("#include <ptlsim.h>\n")
        of.write("#include <memoryHierarchy.h>\n")
        of.write("#include <memoryRequest.h>\n")
        of.write("#include <cacheLines.h>\n")
        of.write("\nnamespace Memory {\n\n")
        typedefs = {}
        for cache, cfg in config["cache"].items():
            # First write all params
            for param,val in cfg["params"].items():
                of.write("#define %s_%s %s\n" % (cache.upper(), param,
                    str(val)))
            # Find the number of sets
            size = get_cache_size(cfg["params"]["SIZE"])
            assoc = cfg["params"]["ASSOC"]
            l_size = cfg["params"]["LINE_SIZE"]
            lat = cfg["params"]["LATENCY"]
            sets = (size / l_size) / assoc
            c_pfx = cache.upper() + "_"

            of.write("#define %s_%s %d\n" % (cache.upper(), "SETS",
                sets))

            # Now write typedef CacheLine
            of.write(cache_typedef_cacheline % (
                c_pfx + "SETS",
                c_pfx + "ASSOC",
                c_pfx + "LINE_SIZE",
                c_pfx + "LATENCY",
                c_pfx))

            typedefs[cache] = c_pfx + "CacheLines"

        # Now write function 'get_cachelines'
        of.write("\nCacheLinesBase* get_cachelines(int cache_type)\n")
        of.write("{\n")
        of.write("\tswitch(cache_type) {\n")
        for cache in config["cache"].keys():
            of.write(cache_case_stmt % (cache.upper(),
                typedefs[cache], cache.upper(), cache.upper()))
        of.write("\t\tdefault: assert(0);\n\t}\n")
        of.write("}\n")
        of.write("};\n")

def gen_output_file(config, options):
    if options.type == "machine":
        generate_machine(config, options)
    elif options.type == "cache" and options.name == "header":
        generate_cache_header(config, options)
    elif options.type == "cache" and options.name == "logic":
        generate_cache_logic(config, options)
    elif options.type == "core":
        write_params_file(config, options)

if __name__ == "__main__":
    _debug("Testing")
    parser = get_arg_parser()
    (options, args) = parser.parse_args()
    check_options(options, parser)
    config = read_config(options.config_filename)
    check_config(config, options)
    gen_output_file(config, options)
    _debug("Done.")
