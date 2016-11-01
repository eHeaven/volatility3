# pdbscan.py -- Scan Volatility Layers for Windows kernel PDB signatures
#
if __name__ == "__main__":
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import struct

from volatility.framework import interfaces

PAGE_SIZE = 0x1000


class PdbSigantureScanner(interfaces.layers.ScannerInterface):
    overlap = 0x4000

    _kernel_pdbs = [
        b"ntkrnlmp.pdb",
        b"ntkrnlpa.pdb",
        b"ntkrpamp.pdb",
        b"ntoskrnl.pdb",
    ]

    _RSDS_format = struct.Struct("<16BI")

    def __call__(self, data, data_offset):
        sig = data.find(b"RSDS")
        pdb_hits = []
        while sig >= 0:
            null = data.find(b'\0', sig + 4 + self._RSDS_format.size)
            if null > -1:
                if (null - sig - self._RSDS_format.size) <= 100:
                    name_offset = sig + 4 + self._RSDS_format.size
                    pdb_name = data[name_offset:null]
                    if pdb_name in self._kernel_pdbs:

                        ## thie ordering is intentional due to mixed endianness in the GUID
                        (g3, g2, g1, g0, g5, g4, g7, g6, g8, g9, ga, gb, gc, gd, ge, gf, a) = \
                            self._RSDS_format.unpack(data[sig + 4:name_offset])

                        GUID = (16 * '{:02X}').format(g0, g1, g2, g3, g4, g5, g6, g7, g8, g9, ga, gb, gc, gd, ge, gf)
                        yield (GUID, a, pdb_name, data_offset + name_offset + sig)
            sig = data.find(b"RSDS", sig + 1)


def scan(ctx, layer_name):
    """Scans through layer_name at context and returns the tuple
       (GUID, age, pdb_name, signature_offset, mz_offset)

       Note that this is automagical and therefore not guaranteed to provide
       correct results.

       The UI should always provide the user an opportunity to specify the
       appropriate types and PDB values themselves
    """
    results = []
    min_pfn = 0
    for (GUID, age, pdb_name, signature_offset) in ctx.memory[layer_name].scan(ctx, PdbSigantureScanner()):
        mz_offset = None
        sig_pfn = signature_offset // PAGE_SIZE

        for i in range(sig_pfn, min_pfn, -1):
            if not ctx.memory[layer_name].is_valid(i * PAGE_SIZE, 2):
                break

            data = ctx.memory.read(layer_name, i * PAGE_SIZE, 2)
            if data == b'MZ':
                mz_offset = i * PAGE_SIZE
                break
        min_pfn = sig_pfn

        results.append((GUID, age, pdb_name, signature_offset, mz_offset))

    return results
