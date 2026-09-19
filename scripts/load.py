from tools import novel, reader

lib = reader.read_library(novel.NOVELS)

novel.build(lib)
