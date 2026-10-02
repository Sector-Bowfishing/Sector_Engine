from .gdal import (GDT_Unknown, GDT_Byte, GDT_UInt16, GDT_Int16, GDT_UInt32, GDT_Int32,
                   GDT_Float32, GDT_Float64, GA_ReadOnly, GA_Update)


def __getattr__(name):
    raise NotImplementedError('osgeo shim: gdalconst.{} not implemented'.format(name))
