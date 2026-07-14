#ifndef FITS_FILE_H
#define FITS_FILE_H

#include <string>
#include <vector>
#include <utility>
#include <cstdint>
#include <fitsio.h>

class FitsFile
{
public:
	FitsFile(std::string fname, std::string hdu_name = "");
	~FitsFile();

	int GetNDim();
	std::vector<long> GetShape();
	long GetSize();
	int GetDataType();

    template <typename T>
	std::vector<T> GetData();

	template <typename T>
	std::vector<T> GetDataCasted();

private:
	std::string GetFitsError();

	fitsfile *m_File;
};

#include "FitsFile.inl"

#endif // FITS_FILE_H
