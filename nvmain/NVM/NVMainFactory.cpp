/*********************
 * created on 2015.5.6
 ********************/

#include "NVM/NVMainFactory.h"
#include "include/Exception.h"
using namespace NVM;
NVMain* NVMainFactory::CreateNVMain( std::string nvm_type) 
{
	NVMain* main_mem = NULL;
	if( nvm_type == "NVMain") main_mem = new NVMain();
	//if( nvm_type == "RBLANVMain") main_mem = new RBLA_NVMain();
	if( nvm_type == "FineNVMain") main_mem = new FineNVMain();
	return main_mem;
}

NVMain* NVMainFactory::CreateNewNVMain( std::string nvm_type)
{
	NVMain* main_mem = CreateNVMain(nvm_type);
	if( !main_mem )
	{
		NVM::Warning("didn't set main memory type! default set NVMain object as main memory");
		main_mem = CreateNVMain("NVMain");
	}
	return main_mem;
}
