# -*- coding: utf-8 -*-
# Advanced MAME Launcher filesystem I/O functions
#

# Copyright (c) 2016-2017 Wintermute0110 <wintermute0110@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# --- Python standard library ---
from __future__ import unicode_literals
from __future__ import division
import json
import io
import codecs
import time
import subprocess
import re
import threading
import copy
# import gc
# import resource # Module not available on Windows

# --- XML stuff ---
# ~~~ cElementTree sometimes fails to parse XML in Kodi's Python interpreter... I don't know why
# import xml.etree.cElementTree as ET

# ~~~ Using ElementTree seems to solve the problem
import xml.etree.ElementTree as ET

# --- AEL packages ---
from constants import *
from utils import *
try:
    from utils_kodi import *
except:
    from utils_kodi_standalone import *

# -------------------------------------------------------------------------------------------------
# Advanced MAME Launcher data model
# -------------------------------------------------------------------------------------------------
# http://xmlwriter.net/xml_guide/attlist_declaration.shtml#CdataEx
# #REQUIRED  The attribute must always be included
# #IMPLIED   The attribute does not have to be included.
#
# Example from MAME 0.190:
#   <!ELEMENT device (instance*, extension*)>
#     <!ATTLIST device type CDATA #REQUIRED>
#     <!ATTLIST device tag CDATA #IMPLIED>
#     <!ATTLIST device fixed_image CDATA #IMPLIED>
#     <!ATTLIST device mandatory CDATA #IMPLIED>
#     <!ATTLIST device interface CDATA #IMPLIED>
#     <!ELEMENT instance EMPTY>
#       <!ATTLIST instance name CDATA #REQUIRED>
#       <!ATTLIST instance briefname CDATA #REQUIRED>
#     <!ELEMENT extension EMPTY>
#       <!ATTLIST extension name CDATA #REQUIRED>
#
# <device> tags. Example of machine aes (Neo Geo AES)
# <device type="memcard" tag="memcard">
#   <instance name="memcard" briefname="memc"/>
#   <extension name="neo"/>
# </device>
# <device type="cartridge" tag="cslot1" interface="neo_cart">
#   <instance name="cartridge" briefname="cart"/>
#   <extension name="bin"/>
# </device>
#
# This is how it is stored:
# devices = [
#   {
#     'att_type' : string,
#     'att_tag' : string,
#     'att_mandatory' : bool,
#     'att_interface' : string,
#     'instance' : {'name' : string, 'briefname' : string}
#     'ext_name' : [string1, string2],
#   }, ...
# ]
#
# Rendering on AML Machine Information text window.
# devices[0, att_type]:
#   att_type: string
#   att_tag: string
#   att_mandatory: unicode(bool)
#   att_interface: string
#   instance: unicode(dictionary),
#   ext_names: unicode(string list),
# devices[1, att_type]: unicode(device[1])
#   ...
#
def fs_new_machine_dic():
    return {
        # >> <machine> attributes
        'sourcefile'     : '',
        'isMechanical'   : False,
        'romof'          : '',
        'sampleof'       : '',
        # >> Other <machine> tags from MAME XML
        'display_tag'    : [],
        'display_type'   : [], # (raster|vector|lcd|unknown) #REQUIRED>
        'display_rotate' : [], # (0|90|180|270) #REQUIRED>
        'control_type'   : [],
        'coins'          : 0,
        'softwarelists'  : [],
        'devices'        : [], # List of dictionaries. See comments avobe.
        # >> Custom AML data
        'catver'         : '', # External catalog
        'nplayers'       : '', # External catalog
        'catlist'        : '', # External catalog
        'genre'          : '', # External catalog
        'bestgames'      : '', # External catalog
        'series'         : '', # External catalog
        'isDead'         : False
    }

#
# Object used in MAME_render_db.json
#   flags -> ROM, CHD, Samples, SoftwareLists, Devices
#
# Status flags meaning:
#   -  Machine doesn't have ROMs | Machine doesn't have Software Lists
#   ?  Machine has own ROMs and ROMs not been scanned
#   r  Machine has own ROMs and ROMs doesn't exist
#   R  Machine has own ROMs and ROMs exists | Machine has Software Lists
#
# Status device flag:
#   -  Machine has no devices
#   d  Machine has device/s but are not mandatory (can be booted without the device).
#   D  Machine has device/s and must be plugged in order to boot.
#
def fs_new_machine_render_dic():
    return {
        # >> <machine> attributes
        'isBIOS'         : False,
        'isDevice'       : False,
        'cloneof'        : '',
        # >> Other <machine> tags from MAME XML
        'description'    : '',
        'year'           : '',
        'manufacturer'   : '',
        'driver_status'  : '',
        # >> Custom AML data
        'genre'          : '',      # Taken from Genre.ini, Catver.ini or Catlist.ini
        'nplayers'       : '',      # Taken from NPlayers.ini
        'flags'          : '-----',
        'plot'           : '',      # Generated from other fields
    }

#
# Object used in MAME_DB_roms.json
# machine_roms = {
#     'machine_name' : {
#         'bios'  : [ ... ],
#         'disks' : [ ... ],
#         'roms'  : [ ... ]
#     }
# }
#
def fs_new_roms_object():
    return {
        'bios'  : [],
        'roms'  : [],
        'disks' : []
    }

def fs_new_bios_dic():
    return {
        'name'        : '',
        'description' : ''
    }

def fs_new_rom_dic():
    return {
        'name'  : '',
        'merge' : '',
        'bios'  : '',
        'size'  : 0,
        'crc'  : '' # crc allows to know if ROM is valid or not
    }

def fs_new_disk_dic():
    return {
        'name'  : '',
        'merge' : '',
        'sha1'  : '' # sha1 allows to know if CHD is valid or not. CHDs don't have crc
    }

#
# Object used in MAME_assets.json, ordered alphabetically.
#
ASSET_MAME_T_LIST  = [
    ('PCB',        'PCBs'),
    ('artpreview', 'artpreviews'),
    ('artwork',    'artwork'),
    ('cabinet',    'cabinets'),
    ('clearlogo',  'clearlogos'),
    ('cpanel',     'cpanels'),
    ('fanart',     'fanarts'),
    ('flyer',      'flyers'),
    ('manual',     'manuals'),
    ('marquee',    'marquees'),
    ('snap',       'snaps'),
    ('title',      'titles'),
    ('trailer',    'videosnaps'),
]

def fs_new_MAME_asset():
    return {
        'PCB'        : '',
        'artpreview' : '',
        'artwork'    : '',
        'cabinet'    : '',
        'clearlogo'  : '',
        'cpanel'     : '',
        'fanart'     : '',
        'flyer'      : '',
        'manual'     : '',
        'marquee'    : '',
        'snap'       : '',
        'title'      : '',
        'trailer'    : '',
    }

# Status flags meaning:
#   ?  SL ROM not scanned
#   r  Missing ROM
#   R  Have ROM
def fs_new_SL_ROM_part():
    return { 'name' : '', 'interface' : '' }

def fs_new_SL_ROM():
    return {
        'description' : '',
        'year'        : '',
        'publisher'   : '',
        'plot'        : '', # Generated from other fields
        'cloneof'     : '',
        'parts'       : [],
        'hasROMs'     : False,
        'hasCHDs'     : False,
        'status_ROM'  : '-',
        'status_CHD'  : '-',
    }

ASSET_SL_T_LIST = [
    ('title',    'titles_SL'),
    ('snap',     'snaps_SL'),
    ('boxfront', 'covers_SL'),
    ('fanart',   'fanarts_SL'),
    ('trailer',  'videosnaps_SL'),
    ('manual',   'manuals_SL'),
]

def fs_new_SL_asset():
    return {
        'title'    : '',
        'snap'     : '',
        'boxfront' : '',
        'fanart'   : '',
        'trailer'  : '',
        'manual'   : '',
    }

def fs_new_control_dic():
    return {
        # --- Filed in when extracting MAME XML ---
        'stats_total_machines' : 0,

        # --- Filed in when building main MAME database ---
        # >> Numerical MAME version. Allows for comparisons like ver_mame >= MAME_VERSION_0190
        # >> MAME string version, as reported by the executable stdout. Example: '0.194 (mame0194)'
        'ver_mame'      : 0,
        'ver_mame_str'  : 'Unknown. MAME database not built',
        'ver_catver'    : 'Unknown. MAME database not built',
        'ver_catlist'   : 'Unknown. MAME database not built',
        'ver_genre'     : 'Unknown. MAME database not built',
        'ver_nplayers'  : 'Unknown. MAME database not built',
        'ver_bestgames' : 'Unknown. MAME database not built',
        'ver_series'    : 'Unknown. MAME database not built',

        # Basic stats
        'stats_processed_machines' : 0,
        'stats_parents'            : 0,
        'stats_clones'             : 0,
        'stats_runnable'           : 0, # Excluding devices (devices are not runnable)
        'stats_runnable_parents'   : 0,
        'stats_runnable_clones'    : 0,
        # Main filters
        'stats_coin'               : 0,
        'stats_coin_parents'       : 0,
        'stats_coin_clones'        : 0,
        'stats_nocoin'             : 0,
        'stats_nocoin_parents'     : 0,
        'stats_nocoin_clones'      : 0,
        'stats_mechanical'         : 0,
        'stats_mechanical_parents' : 0,
        'stats_mechanical_clones'  : 0,
        'stats_dead'               : 0,
        'stats_dead_parents'       : 0,
        'stats_dead_clones'        : 0,
        'stats_devices'            : 0,
        'stats_devices_parents'    : 0,
        'stats_devices_clones'     : 0,
        # Binary filters
        'stats_BIOS'               : 0,
        'stats_BIOS_parents'       : 0,
        'stats_BIOS_clones'        : 0,
        'stats_samples'            : 0,
        'stats_samples_parents'    : 0,
        'stats_samples_clones'     : 0,

        # --- Filed in when building the ROM audit databases ---
        # Number of ROM ZIP files in the Merged, Split or Non-merged sets.
        'audit_MAME_ZIP_files' : 0,
        # Number of CHD files in the Merged, Split or Non-merged sets.
        'audit_MAME_CHD_files' : 0,

        # Number of machines that require one or more ROM ZIP archives to run
        'audit_machine_archives_ROM'         : 0,
        'audit_machine_archives_ROM_parents' : 0,
        'audit_machine_archives_ROM_clones'  : 0,
        # Number of machines that require one or more CHDs to run
        'audit_machine_archives_CHD'         : 0,
        'audit_machine_archives_CHD_parents' : 0,
        'audit_machine_archives_CHD_clones'  : 0,
        # ROM less machines do not need any ZIP archive or CHD to run
        'audit_archive_less'                 : 0,
        'audit_archive_less_parents'         : 0,
        'audit_archive_less_clones'          : 0,

        # --- Filed in when building the SL databases ---
        # Number of SL databases (equal to the number of XML files).
        'stats_SL_XML_files'      : 0,
        'stats_SL_software_items' : 0,
        # Number of SL items that require one or more ROM ZIP archives to run
        'stats_SL_machine_archives_ROM'      : 0,
        # Number of SL items that require one or more CHDs to run
        'stats_SL_machine_archives_CHD'      : 0,

        # --- Filed in by the MAME ROM/CHD/Samples scanner ---
        # >> ROM_Set_ROM_archives.json database
        # Number of ROM ZIP files, including devices.
        'scan_ROM_ZIP_files_total'   : 0,
        'scan_ROM_ZIP_files_have'    : 0,
        'scan_ROM_ZIP_files_missing' : 0,

        # >> ROM_Set_CHD_archives.json database
        # Number of CHD files.
        'scan_CHD_files_total'   : 0,
        'scan_CHD_files_have'    : 0,
        'scan_CHD_files_missing' : 0,

        # >> ROM_Set_machine_archives.json database
        # Number of runnable machines that need one or more ROM ZIP file to run (excluding devices).
        'scan_machine_archives_ROM_total'   : 0,
        # Number of machines you can run, excluding devices.
        'scan_machine_archives_ROM_have'    : 0,
        # Number of machines you cannot run, excluding devices.
        'scan_machine_archives_ROM_missing' : 0,

        # Number of machines that need one or more CHDs to run.
        'scan_machine_archives_CHD_total'   : 0,
        # Number of machines with CHDs you can run.
        'scan_machine_archives_CHD_have'    : 0,
        # Number of machines with CHDs you cannot run.
        'scan_machine_archives_CHD_missing' : 0,

        # >> Samples is not reliable yet
        'scan_Samples_have'    : 0,
        'scan_Samples_total'   : 0,
        'scan_Samples_missing' : 0,

        # --- Filed in by the SL ROM/CHD scanner ---
        'scan_software_archives_ROM_total'   : 0,
        'scan_software_archives_ROM_have'    : 0,
        'scan_software_archives_ROM_missing' : 0,
        'scan_software_archives_CHD_total'   : 0,
        'scan_software_archives_CHD_have'    : 0,
        'scan_software_archives_CHD_missing' : 0,

        # --- Filed in by the MAME asset scanner ---
        'assets_num_MAME_machines'    : 0,
        'assets_PCBs_have'            : 0,
        'assets_PCBs_missing'         : 0,
        'assets_PCBs_alternate'       : 0,
        'assets_artpreview_have'      : 0,
        'assets_artpreview_missing'   : 0,
        'assets_artpreview_alternate' : 0,
        'assets_artwork_have'         : 0,
        'assets_artwork_missing'      : 0,
        'assets_artwork_alternate'    : 0,
        'assets_cabinets_have'        : 0,
        'assets_cabinets_missing'     : 0,
        'assets_cabinets_alternate'   : 0,
        'assets_clearlogos_have'      : 0,
        'assets_clearlogos_missing'   : 0,
        'assets_clearlogos_alternate' : 0,
        'assets_cpanels_have'         : 0,
        'assets_cpanels_missing'      : 0,
        'assets_cpanels_alternate'    : 0,
        'assets_fanarts_have'         : 0,
        'assets_fanarts_missing'      : 0,
        'assets_fanarts_alternate'    : 0,
        'assets_flyers_have'          : 0,
        'assets_flyers_missing'       : 0,
        'assets_flyers_alternate'     : 0,
        'assets_manuals_have'         : 0,
        'assets_manuals_missing'      : 0,
        'assets_manuals_alternate'    : 0,
        'assets_marquees_have'        : 0,
        'assets_marquees_missing'     : 0,
        'assets_marquees_alternate'   : 0,
        'assets_snaps_have'           : 0,
        'assets_snaps_missing'        : 0,
        'assets_snaps_alternate'      : 0,
        'assets_titles_have'          : 0,
        'assets_titles_missing'       : 0,
        'assets_titles_alternate'     : 0,
        'assets_trailers_have'        : 0,
        'assets_trailers_missing'     : 0,
        'assets_trailers_alternate'   : 0,

        # --- Filed in by the SL asset scanner ---
        'assets_SL_num_items'           : 0,
        'assets_SL_titles_have'         : 0,
        'assets_SL_titles_missing'      : 0,
        'assets_SL_titles_alternate'    : 0,
        'assets_SL_snaps_have'          : 0,
        'assets_SL_snaps_missing'       : 0,
        'assets_SL_snaps_alternate'     : 0,
        'assets_SL_boxfronts_have'      : 0,
        'assets_SL_boxfronts_missing'   : 0,
        'assets_SL_boxfronts_alternate' : 0,
        'assets_SL_fanarts_have'        : 0,
        'assets_SL_fanarts_missing'     : 0,
        'assets_SL_fanarts_alternate'   : 0,
        'assets_SL_trailers_have'       : 0,
        'assets_SL_trailers_missing'    : 0,
        'assets_SL_trailers_alternate'  : 0,
        'assets_SL_manuals_have'        : 0,
        'assets_SL_manuals_missing'     : 0,
        'assets_SL_manuals_alternate'   : 0,
    }

def fs_get_cataloged_dic_parents(PATHS, catalog_name):
    if   catalog_name == 'Main':           catalog_dic = fs_load_JSON_file(PATHS.CATALOG_MAIN_PARENT_PATH.getPath())
    elif catalog_name == 'Binary':         catalog_dic = fs_load_JSON_file(PATHS.CATALOG_BINARY_PARENT_PATH.getPath())
    elif catalog_name == 'Catver':         catalog_dic = fs_load_JSON_file(PATHS.CATALOG_CATVER_PARENT_PATH.getPath())
    elif catalog_name == 'Catlist':        catalog_dic = fs_load_JSON_file(PATHS.CATALOG_CATLIST_PARENT_PATH.getPath())
    elif catalog_name == 'Genre':          catalog_dic = fs_load_JSON_file(PATHS.CATALOG_GENRE_PARENT_PATH.getPath())
    elif catalog_name == 'NPlayers':       catalog_dic = fs_load_JSON_file(PATHS.CATALOG_NPLAYERS_PARENT_PATH.getPath())
    elif catalog_name == 'Bestgames':      catalog_dic = fs_load_JSON_file(PATHS.CATALOG_BESTGAMES_PARENT_PATH.getPath())
    elif catalog_name == 'Series':         catalog_dic = fs_load_JSON_file(PATHS.CATALOG_SERIES_PARENT_PATH.getPath())
    elif catalog_name == 'Manufacturer':   catalog_dic = fs_load_JSON_file(PATHS.CATALOG_MANUFACTURER_PARENT_PATH.getPath())
    elif catalog_name == 'Year':           catalog_dic = fs_load_JSON_file(PATHS.CATALOG_YEAR_PARENT_PATH.getPath())
    elif catalog_name == 'Driver':         catalog_dic = fs_load_JSON_file(PATHS.CATALOG_DRIVER_PARENT_PATH.getPath())
    elif catalog_name == 'Controls':       catalog_dic = fs_load_JSON_file(PATHS.CATALOG_CONTROL_PARENT_PATH.getPath())
    elif catalog_name == 'Display_Type':   catalog_dic = fs_load_JSON_file(PATHS.CATALOG_DISPLAY_TYPE_PARENT_PATH.getPath())
    elif catalog_name == 'Display_Rotate': catalog_dic = fs_load_JSON_file(PATHS.CATALOG_DISPLAY_ROTATE_PARENT_PATH.getPath())
    elif catalog_name == 'Devices':        catalog_dic = fs_load_JSON_file(PATHS.CATALOG_DEVICE_LIST_PARENT_PATH.getPath())
    elif catalog_name == 'BySL':           catalog_dic = fs_load_JSON_file(PATHS.CATALOG_SL_PARENT_PATH.getPath())
    elif catalog_name == 'ShortName':      catalog_dic = fs_load_JSON_file(PATHS.CATALOG_SHORTNAME_PARENT_PATH.getPath())
    elif catalog_name == 'LongName':       catalog_dic = fs_load_JSON_file(PATHS.CATALOG_LONGNAME_PARENT_PATH.getPath())
    else:
        log_error('fs_get_cataloged_dic_parents() Unknown catalog_name = "{0}"'.format(catalog_name))

    return catalog_dic

def fs_get_cataloged_dic_all(PATHS, catalog_name):
    if   catalog_name == 'Main':           catalog_dic = fs_load_JSON_file(PATHS.CATALOG_MAIN_ALL_PATH.getPath())
    elif catalog_name == 'Binary':         catalog_dic = fs_load_JSON_file(PATHS.CATALOG_BINARY_ALL_PATH.getPath())
    elif catalog_name == 'Catver':         catalog_dic = fs_load_JSON_file(PATHS.CATALOG_CATVER_ALL_PATH.getPath())
    elif catalog_name == 'Catlist':        catalog_dic = fs_load_JSON_file(PATHS.CATALOG_CATLIST_ALL_PATH.getPath())
    elif catalog_name == 'Genre':          catalog_dic = fs_load_JSON_file(PATHS.CATALOG_GENRE_ALL_PATH.getPath())
    elif catalog_name == 'NPlayers':       catalog_dic = fs_load_JSON_file(PATHS.CATALOG_NPLAYERS_ALL_PATH.getPath())
    elif catalog_name == 'Bestgames':      catalog_dic = fs_load_JSON_file(PATHS.CATALOG_BESTGAMES_ALL_PATH.getPath())
    elif catalog_name == 'Series':         catalog_dic = fs_load_JSON_file(PATHS.CATALOG_SERIES_ALL_PATH.getPath())
    elif catalog_name == 'Manufacturer':   catalog_dic = fs_load_JSON_file(PATHS.CATALOG_MANUFACTURER_ALL_PATH.getPath())
    elif catalog_name == 'Year':           catalog_dic = fs_load_JSON_file(PATHS.CATALOG_YEAR_ALL_PATH.getPath())
    elif catalog_name == 'Driver':         catalog_dic = fs_load_JSON_file(PATHS.CATALOG_DRIVER_ALL_PATH.getPath())
    elif catalog_name == 'Controls':       catalog_dic = fs_load_JSON_file(PATHS.CATALOG_CONTROL_ALL_PATH.getPath())
    elif catalog_name == 'Display_Type':   catalog_dic = fs_load_JSON_file(PATHS.CATALOG_DISPLAY_TYPE_ALL_PATH.getPath())
    elif catalog_name == 'Display_Rotate': catalog_dic = fs_load_JSON_file(PATHS.CATALOG_DISPLAY_ROTATE_ALL_PATH.getPath())
    elif catalog_name == 'Devices':        catalog_dic = fs_load_JSON_file(PATHS.CATALOG_DEVICE_LIST_ALL_PATH.getPath())
    elif catalog_name == 'BySL':           catalog_dic = fs_load_JSON_file(PATHS.CATALOG_SL_ALL_PATH.getPath())
    elif catalog_name == 'ShortName':      catalog_dic = fs_load_JSON_file(PATHS.CATALOG_SHORTNAME_ALL_PATH.getPath())
    elif catalog_name == 'LongName':       catalog_dic = fs_load_JSON_file(PATHS.CATALOG_LONGNAME_ALL_PATH.getPath())
    else:
        log_error('fs_get_cataloged_dic_all() Unknown catalog_name = "{0}"'.format(catalog_name))

    return catalog_dic

# -------------------------------------------------------------------------------------------------
# JSON write/load
# -------------------------------------------------------------------------------------------------
COMPACT_JSON = False
def fs_load_JSON_file(json_filename, verbose = True):
    # --- If file does not exist return empty dictionary ---
    data_dic = {}
    if not os.path.isfile(json_filename):
        log_warning('fs_load_ROMs_JSON() File not found "{0}"'.format(json_filename))
        return data_dic
    if verbose:
        log_debug('fs_load_ROMs_JSON() "{0}"'.format(json_filename))
    with open(json_filename) as file:
        data_dic = json.load(file)

    return data_dic

def fs_write_JSON_file(json_filename, json_data, verbose = True):
    if verbose:
        log_debug('fs_write_JSON_file() "{0}"'.format(json_filename))
    try:
        with io.open(json_filename, 'wt', encoding='utf-8') as file:
            if COMPACT_JSON:
                file.write(unicode(json.dumps(json_data, ensure_ascii = False, sort_keys = True, separators = (',', ':'))))
            else:
                file.write(unicode(json.dumps(json_data, ensure_ascii = False, sort_keys = True, indent = 1, separators = (',', ':'))))
    except OSError:
        gui_kodi_notify('Advanced MAME Launcher - Error', 'Cannot write {0} file (OSError)'.format(roms_json_file))
    except IOError:
        gui_kodi_notify('Advanced MAME Launcher - Error', 'Cannot write {0} file (IOError)'.format(roms_json_file))

# -------------------------------------------------------------------------------------------------
# Threaded JSON loader
# -------------------------------------------------------------------------------------------------
# How to use this code:
#     render_thread = Threaded_Load_JSON(PATHS.RENDER_DB_PATH.getPath())
#     assets_thread = Threaded_Load_JSON(PATHS.MAIN_ASSETS_DB_PATH.getPath())
#     render_thread.start()
#     assets_thread.start()
#     render_thread.join()
#     assets_thread.join()
#     MAME_db_dic     = render_thread.output_dic
#     MAME_assets_dic = assets_thread.output_dic
#
class Threaded_Load_JSON(threading.Thread):
    def __init__(self, json_filename): 
        threading.Thread.__init__(self) 
        self.json_filename = json_filename
 
    def run(self): 
        self.output_dic = fs_load_JSON_file(self.json_filename)

# -------------------------------------------------------------------------------------------------
def fs_extract_MAME_version(PATHS, mame_prog_FN):
    (mame_dir, mame_exec) = os.path.split(mame_prog_FN.getPath())
    log_info('fs_extract_MAME_version() mame_prog_FN "{0}"'.format(mame_prog_FN.getPath()))
    log_debug('fs_extract_MAME_version() mame_dir     "{0}"'.format(mame_dir))
    log_debug('fs_extract_MAME_version() mame_exec    "{0}"'.format(mame_exec))
    with open(PATHS.MAME_STDOUT_VER_PATH.getPath(), 'wb') as out, open(PATHS.MAME_STDERR_VER_PATH.getPath(), 'wb') as err:
        p = subprocess.Popen([mame_prog_FN.getPath(), '-?'], stdout=out, stderr=err, cwd=mame_dir)
        p.wait()

    # --- Check if everything OK ---
    # statinfo = os.stat(PATHS.MAME_XML_PATH.getPath())
    # filesize = statinfo.st_size

    # --- Read version ---
    with open(PATHS.MAME_STDOUT_VER_PATH.getPath()) as f:
        lines = f.readlines()
    version_str = ''
    for line in lines:
        m = re.search('^MAME v([0-9\.]+?) \(([a-z0-9]+?)\)$', line.strip())
        if m:
            version_str = m.group(1)
            break

    return version_str

# MAME_XML_PATH -> (FileName object) path of MAME XML output file.
# mame_prog_FN  -> (FileName object) path to MAME executable.
# Returns filesize -> (int) file size of output MAME.xml
#
def fs_extract_MAME_XML(PATHS, mame_prog_FN):
    (mame_dir, mame_exec) = os.path.split(mame_prog_FN.getPath())
    log_info('fs_extract_MAME_XML() mame_prog_FN "{0}"'.format(mame_prog_FN.getPath()))
    log_debug('fs_extract_MAME_XML() mame_dir     "{0}"'.format(mame_dir))
    log_debug('fs_extract_MAME_XML() mame_exec    "{0}"'.format(mame_exec))
    pDialog = xbmcgui.DialogProgress()
    pDialog_canceled = False
    pDialog.create('Advanced MAME Launcher',
                   'Extracting MAME XML database. Progress bar is not accurate.')
    with open(PATHS.MAME_XML_PATH.getPath(), 'wb') as out, open(PATHS.MAME_STDERR_PATH.getPath(), 'wb') as err:
        p = subprocess.Popen([mame_prog_FN.getPath(), '-listxml'], stdout=out, stderr=err, cwd=mame_dir)
        count = 0
        while p.poll() is None:
            pDialog.update((count * 100) // 100)
            time.sleep(1)
            count = count + 1
    pDialog.close()

    # --- Check if everything OK ---
    statinfo = os.stat(PATHS.MAME_XML_PATH.getPath())
    filesize = statinfo.st_size

    # --- Count number of machines. Useful for progress dialogs ---
    log_info('fs_extract_MAME_XML() Counting number of machines...')
    total_machines = fs_count_MAME_Machines(PATHS)
    log_info('fs_extract_MAME_XML() Found {0} machines.'.format(total_machines))
    # kodi_dialog_OK('Found {0} machines in MAME.xml.'.format(total_machines))

    # -----------------------------------------------------------------------------
    # Create MAME control dictionary
    # -----------------------------------------------------------------------------
    control_dic = fs_new_control_dic()
    control_dic['total_machines'] = total_machines
    fs_write_JSON_file(PATHS.MAIN_CONTROL_PATH.getPath(), control_dic)

    return (filesize, total_machines)

def fs_count_MAME_Machines(PATHS):
    pDialog = xbmcgui.DialogProgress()
    pDialog_canceled = False
    pDialog.create('Advanced MAME Launcher', 'Counting number of MAME machines...')
    pDialog.update(0)
    num_machines = 0
    with open(PATHS.MAME_XML_PATH.getPath(), 'rt') as f:
        for line in f:
            if line.decode('utf-8').find('<machine name=') > 0: num_machines = num_machines + 1
    pDialog.update(100)
    pDialog.close()

    return num_machines

# Valid ROM: ROM has CRC hash
# Valid CHD: CHD has SHA1 hash
def fs_initial_flags(machine, machine_render, m_roms):
    # >> Machine has own ROMs (at least one ROM is valid and has empty 'merge' attribute)
    has_own_ROMs = False
    for rom in m_roms['roms']:
        if not rom['merge'] and rom['crc']:
            has_own_ROMs = True
            break
    flag_ROM = '?' if has_own_ROMs else '-'

    # >> Machine has own CHDs
    has_own_CHDs = False
    for rom in m_roms['disks']:
        if not rom['merge'] and rom['sha1']:
            has_own_CHDs = True
            break
    flag_CHD = '?' if has_own_CHDs else '-'

    # >> Samples flag
    flag_Samples = '?' if machine['sampleof'] else '-'

    # >> Software List flag
    flag_SL = 'L' if machine['softwarelists'] else '-'

    # >> Devices flag
    if machine['devices']:
        num_dev_mandatory = 0
        for device in machine['devices']:
            if device['att_mandatory']: 
                flag_Devices = 'D'
                num_dev_mandatory += 1
            else: 
                flag_Devices  = 'd'
        if num_dev_mandatory > 2:
            message = 'Machine {0} has {1} mandatory devices'.format(machine_name, num_dev_mandatory)
            raise CriticalError(message)
    else:
        flag_Devices  = '-'

    return '{0}{1}{2}{3}{4}'.format(flag_ROM, flag_CHD, flag_Samples, flag_SL, flag_Devices)

#
# Update m_render using Python pass by assignment.
# Remember that strings are inmutable!
#
def fs_set_ROM_flag(m_render, new_ROM_flag):
    old_flags_str = m_render['flags']
    flag_ROM      = old_flags_str[0]
    flag_CHD      = old_flags_str[1]
    flag_Samples  = old_flags_str[2]
    flag_SL       = old_flags_str[3]
    flag_Devices  = old_flags_str[4]
    flag_ROM      = new_ROM_flag
    m_render['flags'] = '{0}{1}{2}{3}{4}'.format(flag_ROM, flag_CHD, flag_Samples, flag_SL, flag_Devices)

def fs_set_CHD_flag(m_render, new_CHD_flag):
    old_flags_str = m_render['flags']
    flag_ROM      = old_flags_str[0]
    flag_CHD      = old_flags_str[1]
    flag_Samples  = old_flags_str[2]
    flag_SL       = old_flags_str[3]
    flag_Devices  = old_flags_str[4]
    flag_CHD      = new_CHD_flag
    m_render['flags'] = '{0}{1}{2}{3}{4}'.format(flag_ROM, flag_CHD, flag_Samples, flag_SL, flag_Devices)

def fs_set_Sample_flag(m_render, new_Sample_flag):
    old_flags_str = m_render['flags']
    flag_ROM      = old_flags_str[0]
    flag_CHD      = old_flags_str[1]
    flag_Samples  = old_flags_str[2]
    flag_SL       = old_flags_str[3]
    flag_Devices  = old_flags_str[4]
    flag_Samples  = new_Sample_flag
    m_render['flags'] = '{0}{1}{2}{3}{4}'.format(flag_ROM, flag_CHD, flag_Samples, flag_SL, flag_Devices)

def fs_build_catalog_helper(catalog_parents, catalog_all, machines, machines_render, main_pclone_dic, db_field):
    for parent_name in main_pclone_dic:
        # >> Skip device machines in catalogs.
        if machines_render[parent_name]['isDevice']: continue
        catalog_key = machines[parent_name][db_field]
        if catalog_key in catalog_parents:
            catalog_parents[catalog_key].append(parent_name)
            catalog_all[catalog_key].append(parent_name)
            catalog_all[catalog_key].extend(main_pclone_dic[parent_name])
        else:
            catalog_parents[catalog_key] = [ parent_name ]
            catalog_all[catalog_key] = [ parent_name ]
            catalog_all[catalog_key].extend(main_pclone_dic[parent_name])
    # >> Sort lists alpahbetically
    for catalog_key in catalog_all: catalog_all[catalog_key].sort()
    for catalog_key in catalog_parents: catalog_parents[catalog_key].sort()

# -------------------------------------------------------------------------------------------------
# Hashed databases. Useful when only one item in a big dictionary is required.
# -------------------------------------------------------------------------------------------------
# Hash database with 256 elements (2 hex digits)
def fs_build_main_hashed_db(PATHS, machines, machines_render, pDialog):
    log_info('fs_build_main_hashed_db() Building main hashed database ...')

    # machine_name -> MD5 -> take two letters -> aa.json, ab.json, ...
    # A) First create an index
    #    db_main_hash_idx = { 'machine_name' : 'aa', ... }
    # B) Then traverse a list [0, 1, ..., f] and write the machines in that sub database section.
    pDialog.create('Advanced MAME Launcher', 'Building main hashed database ...')
    db_main_hash_idx = {}
    for key in machines:
        md5_str = hashlib.md5(key).hexdigest()
        db_name = md5_str[0:2] # WARNING Python slicing does not work like in C/C++!
        db_main_hash_idx[key] = db_name
        # log_debug('Machine {0:20s} / hash {1} / db file {2}'.format(key, md5_str, db_name))
    pDialog.update(100)
    pDialog.close()

    log_info('Building main hashed database JSON files ...')
    hex_digits = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f']
    distributed_db_files = []
    for u in range(len(hex_digits)):
        for v in range(len(hex_digits)):
            db_str = '{0}{1}'.format(hex_digits[u], hex_digits[v])
            distributed_db_files.append(db_str)
    pDialog.create('Advanced MAME Launcher', 'Building main hashed database JSON files ...')
    num_items = len(distributed_db_files)
    item_count = 0
    for db_prefix in distributed_db_files:
        # log_debug('db prefix {0}'.format(db_prefix))
        # --- Generate dictionary in this JSON file ---
        hashed_db_dic = {}
        for key in db_main_hash_idx:
            if db_main_hash_idx[key] == db_prefix:
                machine_dic = machines[key].copy()
                # >> returns None because it mutates machine_dic
                machine_dic.update(machines_render[key])
                hashed_db_dic[key] = machine_dic
        # --- Save JSON file ---
        hash_DB_FN = PATHS.MAIN_DB_HASH_DIR.pjoin(db_prefix + '.json')
        fs_write_JSON_file(hash_DB_FN.getPath(), hashed_db_dic)
        item_count += 1
        pDialog.update(int((item_count*100) / num_items))
    pDialog.close()

#
# Retrieves machine from distributed database.
# This is very quick for retrieving individual machines, very slow for multiple machines.
#
def fs_get_machine_main_db_hash(PATHS, machine_name):
    log_debug('fs_get_machine_main_db_hash() machine {0}'.format(machine_name))
    md5_str = hashlib.md5(machine_name).hexdigest()
    # WARNING Python slicing does not work like in C/C++!
    hash_DB_FN = PATHS.MAIN_DB_HASH_DIR.pjoin(md5_str[0:2] + '.json')
    hashed_db_dic = fs_load_JSON_file(hash_DB_FN.getPath())

    return hashed_db_dic[machine_name]

# -------------------------------------------------------------------------------------------------
# ROM cache
# -------------------------------------------------------------------------------------------------
def fs_rom_cache_get_hash(catalog_name, category_name):
    prop_key = '{0} - {1}'.format(catalog_name, category_name)

    return hashlib.md5(prop_key).hexdigest()

def fs_build_ROM_cache(PATHS, machines, machines_render, cache_index_dic, pDialog):
    log_info('fs_build_ROM_cache() Building ROM cache ...')

    pDialog.create('Advanced MAME Launcher', ' ', ' ')
    num_catalogs = len(cache_index_dic)
    catalog_count = 1
    for catalog_name in cache_index_dic:
        catalog_index_dic = cache_index_dic[catalog_name]
        catalog_all = fs_get_cataloged_dic_all(PATHS, catalog_name)

        pdialog_line1 = 'Building {0} ROM cache ({1} of {2}) ...'.format(
            catalog_name, catalog_count, num_catalogs)
        pDialog.update(0, pdialog_line1)
        total_items = len(catalog_index_dic)
        item_count = 0
        for catalog_key in catalog_index_dic:
            hash_str = catalog_index_dic[catalog_key]['hash']
            log_verb('fs_build_ROM_cache() Catalog "{0}" --- Key "{1}"'.format(catalog_name, catalog_key))
            log_verb('fs_build_ROM_cache() hash {0}'.format(hash_str))

            # >> Build all machines cache
            m_render_all_dic = {}
            for machine_name in catalog_all[catalog_key]:
                m_render_all_dic[machine_name] = machines_render[machine_name]
            ROMs_all_FN = PATHS.CACHE_DIR.pjoin(hash_str + '_ROMs.json')
            fs_write_JSON_file(ROMs_all_FN.getPath(), m_render_all_dic)

            # >> Progress dialog
            item_count += 1
            pDialog.update((item_count*100) // total_items, pdialog_line1)
        # >> Progress dialog
        catalog_count += 1
    pDialog.close()

def fs_load_roms_all(PATHS, cache_index_dic, catalog_name, category_name):
    hash_str = cache_index_dic[catalog_name][category_name]['hash']
    ROMs_all_FN = PATHS.CACHE_DIR.pjoin(hash_str + '_ROMs.json')

    return fs_load_JSON_file(ROMs_all_FN.getPath())

# -------------------------------------------------------------------------------------------------
# Asset cache
# -------------------------------------------------------------------------------------------------
def fs_build_asset_cache(PATHS, assets_dic, cache_index_dic, pDialog):
    log_info('fs_build_asset_cache() Building Asset cache ...')

    pDialog.create('Advanced MAME Launcher', ' ', ' ')
    num_catalogs = len(cache_index_dic)
    catalog_count = 1
    for catalog_name in cache_index_dic:
        catalog_index_dic = cache_index_dic[catalog_name]
        catalog_all = fs_get_cataloged_dic_all(PATHS, catalog_name)

        pdialog_line1 = 'Building {0} asset cache ({1} of {2}) ...'.format(
            catalog_name, catalog_count, num_catalogs)
        pDialog.update(0, pdialog_line1)
        total_items = len(catalog_index_dic)
        item_count = 0
        for catalog_key in catalog_index_dic:
            hash_str = catalog_index_dic[catalog_key]['hash']
            log_verb('fs_build_asset_cache() Catalog "{0}" --- Key "{1}"'.format(catalog_name, catalog_key))
            log_verb('fs_build_asset_cache() hash {0}'.format(hash_str))

            # >> Build all machines cache
            m_assets_all_dic = {}
            for machine_name in catalog_all[catalog_key]:
                m_assets_all_dic[machine_name] = assets_dic[machine_name]
            ROMs_all_FN = PATHS.CACHE_DIR.pjoin(hash_str + '_assets.json')
            fs_write_JSON_file(ROMs_all_FN.getPath(), m_assets_all_dic)

            # >> Progress dialog
            item_count += 1
            pDialog.update((item_count*100) // total_items, pdialog_line1)
        # >> Progress dialog
        catalog_count += 1
    pDialog.close()

def fs_load_assets_all(PATHS, cache_index_dic, catalog_name, category_name):
    hash_str = cache_index_dic[catalog_name][category_name]['hash']
    ROMs_all_FN = PATHS.CACHE_DIR.pjoin(hash_str + '_assets.json')

    return fs_load_JSON_file(ROMs_all_FN.getPath())
