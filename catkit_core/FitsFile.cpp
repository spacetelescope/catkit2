#include "FitsFile.h"

#include <stdexcept>

FitsFile::FitsFile(std::string fname, std::string hdu_name)
{
	int status;

	if (fits_open_file(&m_File, fname.c_str(), READONLY, &status))
	{
		fits_report_error(stderr, status);
		throw std::runtime_error("Failed to open FITS file.");
	}

	if (fits_movnam_hdu(m_File, IMAGE_HDU, const_cast<char *>(hdu_name.c_str()), 0, &status))
	{
		fits_report_error(stderr, status);
		fits_close_file(m_File, &status);
		throw std::runtime_error("Failed to move to HDU.");
	}
}

FitsFile::~FitsFile()
{
	int status;
	fits_close_file(m_File, &status);
}

int FitsFile::GetNDim()
{
	int status;
	int naxis;
	if (fits_get_img_dim(m_File, &naxis, &status))
	{
		fits_report_error(stderr, status);
		throw std::runtime_error("Failed to get image dimension.");
	}

	return naxis;
}

std::vector<long> FitsFile::GetShape()
{
	int status;

	std::vector<long> shape;
	shape.resize(GetNDim());

	if (fits_get_img_size(m_File, shape.size(), shape.data(), &status))
	{
		fits_report_error(stderr, status);
		throw std::runtime_error("Failed to get image shape.");
	}

	return shape;
}

long FitsFile::GetSize()
{
	long size = 1;
	for (auto s : GetShape())
		size *= s;

	return size;
}

int FitsFile::GetDataType()
{
	int status;
	int bitpix;
	if (fits_get_img_type(m_File, &bitpix, &status))
	{
		fits_report_error(stderr, status);
		throw std::runtime_error("Failed to get image type.");
	}

	return bitpix;
}

std::string FitsFile::GetFitsError()
{
	std::string error;
	char error_message[80];

	while (fits_read_errmsg(error_message))
		error += error_message;
		error += "\n";

	return error;
}
