#ifndef CACAO_STREAM_H
#define CACAO_STREAM_H

#ifdef USE_MILK

#include "ImageStreamIO.h"
using CacaoStream = IMAGE;

#else

// Use a placeholder for the CacaoStream struct.
using CacaoStream = void;

#endif

#endif // CACAO_STREAM_H
