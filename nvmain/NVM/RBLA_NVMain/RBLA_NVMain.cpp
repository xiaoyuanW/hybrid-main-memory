/*******************************************************************************
* Copyright (c) 2012-2014, The Microsystems Design Labratory (MDL)
* Department of Computer Science and Engineering, The Pennsylvania State University
* All rights reserved.
* 
* This source code is part of NVMain - A cycle accurate timing, bit accurate
* energy simulator for both volatile (e.g., DRAM) and non-volatile memory
* (e.g., PCRAM). The source code is free and you can redistribute and/or
* modify it by providing that the following conditions are met:
* 
*  1) Redistributions of source code must retain the above copyright notice,
*     this list of conditions and the following disclaimer.
* 
*  2) Redistributions in binary form must reproduce the above copyright notice,
*     this list of conditions and the following disclaimer in the documentation
*     and/or other materials provided with the distribution.
* 
* THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
* ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
* WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
* DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
* FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
* DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
* SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
* CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
* OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
* OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
* 
* Author list: 
*   Matt Poremba    ( Email: mrp5060 at psu dot edu 
*                     Website: http://www.cse.psu.edu/~poremba/ )
*******************************************************************************/

#include "NVM/RBLA_NVMain/RBLA_NVMain.h"
#include "src/Config.h"
#include "src/AddressTranslator.h"
#include "src/Interconnect.h"
#include "src/SimInterface.h"
#include "src/EventQueue.h"
#include "Interconnect/InterconnectFactory.h"
#include "MemControl/MemoryControllerFactory.h"
#include "traceWriter/TraceWriterFactory.h"
#include "Decoders/DecoderFactory.h"
#include "Utils/HookFactory.h"
#include "include/NVMainRequest.h"
#include "include/NVMHelpers.h"
#include "Prefetchers/PrefetcherFactory.h"
#include "include/Exception.h"
//#include "Simulators/gem5/nvmain_mem.hh"
#include "Utils/CommonMigrator/CommonMigrator.h"
#include <sstream>
#include <cassert>

using namespace NVM;


uint64_t RBLA_NVMain::migra_thres = 20 ;
Action RBLA_NVMain::pre_action = INCREMENT;
uint64_t RBLA_NVMain::pre_net_benefit = 0;
RBLA_NVMain::RBLA_NVMain( )
{
	stats_table_entry = 16;
	write_incre = 2;
	read_incre = 1;
	update_interval = 1000;
	migrator_name_ = "RBLANVMain";
	migrated_pages_ = 0;
	
	statsHit = 0;
	statsMiss = 0;
	//rb_hit = 0;
	//rb_miss = 0;
	rb_hitrate = 0.0;
	clean_rb_miss_ = dirty_rb_miss_ = 0;
	tdram_hit_ = tdram_miss_ = -1;
	tpcm_hit_ = tpcm_clean_miss_ = tpcm_miss_ = -1;
	src_channel = 0;
	row_buffer_miss = 0;
	row_buffer_hits = 0;
}


RBLA_NVMain::~RBLA_NVMain( )
{    
}

void RBLA_NVMain::SetConfig( Config *conf, std::string memoryName, bool createChildren )
{
	NVMain::SetConfig( conf , memoryName , createChildren );
	//get tBurst,RATE,BusWidth
	if( config->KeyExists("StatsTableEntry"))
		stats_table_entry = static_cast<uint64_t>( config->GetValue("StatsTableEntry") );
	if(config->KeyExists("WriteIncrement"))
		write_incre = static_cast<uint64_t>(config->GetValue("WriteIncrement"));
	if(config->KeyExists("ReadIncrement"))
		read_incre = static_cast<uint64_t>(config->GetValue("ReadIncrement"));
	if(config->KeyExists("UpdateInterval"))
		update_interval = static_cast<uint64_t>(config->GetValue("UpdateInterval"));
	if(config->KeyExists("MigrationThres"))
		migra_thres = static_cast<uint64_t>(config->GetValue("MigrationThres"));
	if( config->KeyExists("MigratorName"))
		migrator_name_ = config->GetString("MigratorName");
	if( config->KeyExists("PromotionChannel"))
		dst_channel = config->GetValue("PromotionChannel");
	else
		dst_channel = config->GetValue("CHANNELS")-1;
	 if ( src_channel == dst_channel)
	 {
		 src_channel++;
	 }
	//tpcm_hit_ = memoryControllers[src_channel]->GetHitCycles();	
	tpcm_clean_miss_ = memoryControllers[src_channel]->GetMissCycles();
	tpcm_miss_ = memoryControllers[src_channel]->GetDirtyMissCycles();

	//tdram_hit_ = memoryControllers[dst_channel]->GetHitCycles();
	tdram_miss_ = memoryControllers[dst_channel]->GetMissCycles();
	tdiff_dirty_ = tpcm_miss_ - tdram_miss_;
	tdiff_clean_ = tpcm_clean_miss_ - tdram_miss_;

	std::cout<<" pcm time of clean miss is "<<tpcm_clean_miss_<<std::endl;
	std::cout<<"diff time of dirty miss is "<<tdiff_dirty_<<std::endl;
	std::cout<<"diff time of clean miss is "<<tdiff_clean_<<std::endl;
	//create stats table
	statsTable = std::auto_ptr<StatsStore>( new StatsStore(stats_table_entry));
}


bool RBLA_NVMain::IssueCommand( NVMainRequest *request)
{
	Migrator* migrator_trans = dynamic_cast< Migrator*>(this->GetDecoder());
	//migrator decoder must be Migrator object
	assert( migrator_trans);
	if ( migrator_trans->IsMigrated( request->address) )
	{
		request->is_migrated = true;
	}
   return NVMain::IssueCommand( request );
}


bool RBLA_NVMain::RequestComplete( NVMainRequest *request )
{
    bool rv = false;
    if( request->owner == this )
    {
        if( request->isPrefetch )
        {
            /* Place in prefetch buffer. */
            if( prefetchBuffer.size() >= p->PrefetchBufferSize )
            {
                unsuccessfulPrefetches++;
                delete prefetchBuffer.front();
                prefetchBuffer.pop_front();
            }
            prefetchBuffer.push_back( request );
            rv = true;
        }
        else if(request->type==MIGRATION)
		//else if(request->tag==MIGRATION)
        {
            delete request;
			migrated_pages_++;
            rv = true;
        }
    }
    else
    {
		//*******************memory access traces
		int miss_type = 0;
		if( request->rbHit == true)
		{
			miss_type = 0;
		}
		else if( request->rbHit == false)
		{
			if( request->dirty_miss == true )
				miss_type = 2;
			else
				miss_type = 1;
		}
		file<<request->is_migrated<<" "<< miss_type<<" "
			<<request->address.GetChannel() <<" "
			<<request->address.GetBank()<<" "<<request->address.GetRow()<<" "
			<<request->address.GetCol()<<std::endl;
		//*******************traces end
		//if row buffer miss , modify stats table and decide whether to migrate
	  	
	 if(request->rbHit == false )
	  {
			row_buffer_miss++;
			if( request->is_migrated )
			std::cout<<"row buffer miss : request is_migrated, channel is"<<request->address.GetChannel()<<std::endl;

			if( ( request->is_migrated == false)&&(request->address.GetChannel()!= dst_channel))
			{
				bool ret = false;
				uint64_t row_num = GetRowNum( request );
				if( request->type==READ || request->type==READ_PRECHARGE) 
					ret = UpdateStatsTable( row_num , read_incre );
				if(request->type==WRITE || request->type==WRITE_PRECHARGE)
					ret = UpdateStatsTable( row_num , write_incre);
				//can migration
				if( ret )
				 {
					std::cout<<"can migration : "<<request->address.GetChannel()<<std::endl;
					// AdjustMigrateThres();
					 //statsTable->Clear(); //refresh row buffer miss times of all entries
					 CommonMigrator* migrator = dynamic_cast<CommonMigrator*>(NVMainMemory::GetHookByname( migrator_name_));		 
					 if( migrator )
					{
					   //create new request,issue to Migrator
					   NVMainRequest *req = new NVMainRequest();
					   *req = *request;
					   req->type = MIGRATION;
					   req->owner = this;
					   migrator->SetParent(this);
					   migrator->IssueCommand(req);
					   migrated_pages_++;

					   int migrate_source = 2;
					  if( request->dirty_miss == true )
						miss_type = 2;
				      else
						miss_type = 1;
					  std::cout<<"migrating "<<migrate_source<<" miss type:"<<miss_type<<std::endl;
				file<<migrate_source<<" "<<miss_type<<" "
					<<request->address.GetChannel() <<" "
					<<request->address.GetBank()<<" "<<request->address.GetRow()<<" "
					<<request->address.GetCol()<<std::endl;
				   }
				}
			}
		}
		if(request->rbHit==true)
		{
			if( request->is_migrated )
				std::cout<<" request is migrated: row buffer hit, channel"<<request->address.GetChannel()<<std::endl;
			row_buffer_hits++;
		}
	
		if( (request->is_migrated) )
		{
			std::cout<<"request is migrated"<<std::endl;
			if( request->rbHit == false )
			{
				if( request->dirty_miss )
				{
					dirty_rb_miss_++;	
					std::cout<<"dirty row buffer miss"<<std::endl;
				}
				else
				{
					clean_rb_miss_++;
					std::cout<<"clean row buffer miss"<<std::endl;
				}
			}
		}
		rv = GetParent( )->RequestComplete( request );
	}
    return rv;
}


void RBLA_NVMain::Cycle( ncycle_t steps )
{
	    assert( !p->EventDriven );
	 //Previous errors can prevent config from being set.
	 //Likewise, if the first memoryController is NULL, 
	 //so are all the others, so return here instead of seg faulting.
		if( !config || !memoryControllers )
	      return;
	 
     // Sync the memory clock with the cpu clock. 
	    double cpuFreq = static_cast<double>(p->CPUFreq);
	    double busFreq = static_cast<double>(p->CLK);
		 
        syncValue += static_cast<double>( busFreq / cpuFreq );
        if( syncValue >= 1.0f )
	         syncValue -= 1.0f;
        else
			return;
	    for( unsigned int i = 0; i < numChannels; i++ )
	         memoryControllers[i]->Cycle( 1 );
	    GetEventQueue()->Loop( steps );
		uint64_t cur_cycle = GetEventQueue()->GetCurrentCycle();
		//every update_interval ,call function "AdjustMigrateThres" adjust migra_thres
		if( !(cur_cycle%update_interval) )
		{
			AdjustMigrateThres();
			statsTable->Clear(); //refresh row buffer miss times of all entries
		}
}

void RBLA_NVMain::RegisterStats( )
{
	AddStat(migrated_pages_);
	AddStat( statsHit );
	AddStat( statsMiss);
	AddStat( statsHitRate );
	AddStat( row_buffer_hits);
	AddStat( row_buffer_miss);
	AddStat( rb_hitrate);
	AddStat( dirty_rb_miss_);
	AddStat( clean_rb_miss_);
	NVMain::RegisterStats();
}

void RBLA_NVMain::CalculateStats( )
{
	statsHitRate = double(statsHit)/double(statsHit+statsMiss);
	if( row_buffer_hits + row_buffer_miss >0)
		rb_hitrate = (double)row_buffer_hits/(row_buffer_hits + row_buffer_miss);
	for( int i =0; i< numChannels ; i++)
	    memoryControllers[i]->CalculateStats( );
	NVMain::CalculateStats();
}

/////////////////////////////////////////////////////////added on 2015/5/4
/*
 * function : update stats table when row buffer miss 
 * @row_num : row address (key of stats table)
 * @incre_num : when row buffer miss , increment num of miss_time
 *
 */
bool RBLA_NVMain::UpdateStatsTable ( uint64_t row_num , uint64_t incre_num)
{
	bool can_migration = false;
	uint64_t entry_id;
	StatsStoreBlock* stat_blk;
	//stats table hit
	if( (stat_blk = statsTable->FindEntry(row_num)))
	{
		statsHit++;
	}
	//stats table miss
	else
	{
		stat_blk = statsTable->FindVictim(entry_id);
		statsTable->Install(stat_blk , row_num);
		statsMiss++;
	}
	if(stat_blk)
	{
		statsTable->IncreMissTime( stat_blk , incre_num );
		if(stat_blk->miss_time >= migra_thres)
		{
				//std::cout<<"row:"<< row_num <<"miss time:"<< stat_blk->miss_time<<std::endl;
				//std::cout<<"over migration threshold,can migration"<<std::endl;
				//after migration set miss_time to 0?
				stat_blk->miss_time = 0;
				can_migration = true;
		}
	}
	return can_migration;
}


void RBLA_NVMain::AdjustMigrateThres()
{
	int64_t net_benefit = CalculateBenefit();
	if( migra_thres>0 )
	{
		if( (net_benefit < 0)&&( net_benefit < pre_net_benefit ))
		{
				migra_thres += 3;
				pre_action = INCREMENT;
		}
		else if ( (net_benefit > pre_net_benefit)&&( net_benefit!=0))
		{
			if( pre_action == INCREMENT)
				migra_thres++;
			else
				migra_thres--;
		}
		else if( (net_benefit < pre_net_benefit)&&(net_benefit!=0))
		{
			if(pre_action == INCREMENT)
			{
				migra_thres--;
				pre_action = DECREMENT;
			}
			else
			{
				migra_thres++;
				pre_action = INCREMENT;
			}
		}
		std::cout<<"Adjust: migration threshold : migration threshold is:"<<migra_thres<<std::endl;
		pre_net_benefit = net_benefit;
	}
}


int64_t RBLA_NVMain::CalculateBenefit()
{
	
	int64_t benefit = 0;
	benefit = dirty_rb_miss_*tdiff_dirty_ + clean_rb_miss_* tdiff_clean_
			  - CommonMigrator::migration_cycles_;
	std::cout<<"benefit is "<<benefit<<std::endl;
	return benefit;
	return 1.0;
}


uint64_t RBLA_NVMain::GetRowNum(NVMainRequest* req)
{
	uint64_t row , col , rank , bank , channel , subarray;
	translator->Translate(req->address.GetPhysicalAddress() ,  \
			&row , &col , &bank , &rank , &channel , &subarray);
	//return row address
	return translator->ReverseTranslate(row , 0 , bank , rank , channel , subarray);
}

