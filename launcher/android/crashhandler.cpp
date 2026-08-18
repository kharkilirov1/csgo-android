/*
Copyright (C) 2022 nillerusr

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of 
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
*/

#include <stdio.h>
#include <string.h>
#include <dlfcn.h>
#include <pthread.h>
#include <unwind.h>
#include <android/log.h>
#include "tier0/dbg.h"
#include <stdlib.h>
#include <inttypes.h>
#include "libunwind/libunwind.h"

struct sigaction old_sa;

#define IN_LIBGCC2 1 // means we want to define __cxxabiv1::__cxa_demangle
namespace __cxxabiv1
{
	extern "C"
	{
		#include "demangle/cp-demangle.c"
	}
}

#define MAX_FRAMES 2048

struct backtrace_t
{
	int count;
	uintptr_t frames[MAX_FRAMES];
};

// Crash output goes to logcat AND stderr. stderr is redirected into
// VALVE_GAME_PATH/launcher.log at startup (see main.cpp), so the backtrace
// reaches users who have no adb - write() straight to the fd because stdio
// isn't async-signal-safe inside a crash handler.
static void LogLine( const char *msg )
{
	__android_log_print( ANDROID_LOG_DEBUG, "SRCENG", "%s", msg );
	write( STDERR_FILENO, msg, strlen( msg ) );
}
#define Log(msg) LogLine(msg);

void printPC(void *pc)
{
	char message[4096];

	const char* symbol = "unknown";

	Dl_info info = { 0 };
	const char *fname = "unknown";

	if( dladdr(pc, &info) <= 0 )
	{
		snprintf( message, sizeof(message), "0x%" PRIXPTR "\n", (uintptr_t)pc );
		Log(message);
		return;
	}

	if( info.dli_fname )
		fname = info.dli_fname;

	if( info.dli_sname )
		symbol = info.dli_sname;

	int status = 0;
	char *demangled = __cxxabiv1::__cxa_demangle(symbol, 0, 0, &status);

	if( NULL != demangled && 0 == status )
		symbol = demangled;

	uintptr_t relative_addr = (uintptr_t)pc - (uintptr_t)info.dli_fbase;

	snprintf( message, sizeof(message), "0x%" PRIXPTR ":\t%s (base=0x%" PRIXPTR ", %s)\n", relative_addr, symbol, (uintptr_t)info.dli_fbase, fname );
	Log(message);
}

_Unwind_Reason_Code UnwindBacktraceCallback(struct _Unwind_Context* unwind_context, void* state_voidp)
{
	uintptr_t pc = _Unwind_GetIP(unwind_context);
	backtrace_t *bt = (backtrace_t*)state_voidp;

	// Print every frame as it is unwound, BEFORE the unwinder touches the
	// next frame: a nested fault inside _Unwind_Backtrace kills the process
	// on the spot (the signal is blocked while the handler runs), and frames
	// printed eagerly are the ones we keep. Collecting into a buffer first
	// and printing afterwards loses the whole backtrace in that case.
	printPC( (void*)pc );

	if( bt->count < MAX_FRAMES )
		bt->frames[bt->count++] = pc;
	else
		return _URC_END_OF_STACK;

	return _URC_NO_REASON;
}

// Fallback unwinder for the aarch64 case: walk the frame-pointer chain
// (x29) directly. Debug builds keep frame pointers, so this is reliable and
// does not depend on .eh_frame or the C++ unwind runtime at all. Stops at
// the first frame that does not look like a valid chain.
static int UnwindByFramePointer( uintptr_t fp, uintptr_t sp )
{
	int count = 0;
	const uintptr_t kMaxFrames = 256;

	for( int i = 0; i < (int)kMaxFrames && fp != 0; i++ )
	{
		// Sanity checks: the frame record must live between the stack
		// pointer and the top of the stack, and must be aligned.
		if( fp < sp || ( fp & 0xF ) != 0 )
			break;

		uintptr_t next_fp = 0;
		uintptr_t ret_addr = 0;

		// copy 16 bytes by hand - memcpy is not guaranteed async-signal-safe
		const volatile uintptr_t *rec = (const volatile uintptr_t *)fp;
		next_fp = rec[0];
		ret_addr = rec[1];

		// A return address in the low 4KB is a null-ish return, stop.
		if( ret_addr < 0x1000 )
			break;

		printPC( (void*)ret_addr );
		count++;

		if( next_fp <= fp )
			break;

		fp = next_fp;
	}

	return count;
}

static void CrashHandler( int sig, siginfo_t *si, void *uc)
{
	static char message[4096];

	const ucontext_t* signal_ucontext = (ucontext_t*)uc;
	const mcontext_t* signal_mcontext = &(signal_ucontext->uc_mcontext);

	// Print the header and the raw register state BEFORE attempting any stack
	// unwinding: a nested fault inside the unwinder kills the process on the
	// spot (the signal is blocked while the handler runs), so anything printed
	// after the unwind can be lost. pc/lr alone are enough to locate a crash.
	Log(">>> crash report begin\n");

	snprintf(message, sizeof(message), "Signal=%d, errno=%d, code=%d, addr=0x%" PRIXPTR "\n", sig, si->si_errno, si->si_code, (uintptr_t)si->si_addr);
	Log(message);

#ifdef __aarch64__
	snprintf(message, sizeof(message), "pc=0x%" PRIXPTR " lr=0x%" PRIXPTR " sp=0x%" PRIXPTR " fault=0x%" PRIXPTR "\n",
		(uintptr_t)signal_mcontext->pc, (uintptr_t)signal_mcontext->regs[30],
		(uintptr_t)signal_mcontext->sp, (uintptr_t)signal_mcontext->fault_address);
	Log(message);
	// Full register dump: x0 is the faulting 'this'/container pointer, x29
	// the frame pointer for the fallback unwinder.
	snprintf(message, sizeof(message),
		"x0=0x%" PRIXPTR " x1=0x%" PRIXPTR " x2=0x%" PRIXPTR " x3=0x%" PRIXPTR "\n"
		"x4=0x%" PRIXPTR " x5=0x%" PRIXPTR " x6=0x%" PRIXPTR " x7=0x%" PRIXPTR "\n"
		"x8=0x%" PRIXPTR " x9=0x%" PRIXPTR " x10=0x%" PRIXPTR " x11=0x%" PRIXPTR "\n"
		"x12=0x%" PRIXPTR " x13=0x%" PRIXPTR " x14=0x%" PRIXPTR " x15=0x%" PRIXPTR "\n"
		"x16=0x%" PRIXPTR " x17=0x%" PRIXPTR " x18=0x%" PRIXPTR " x19=0x%" PRIXPTR "\n"
		"x20=0x%" PRIXPTR " x21=0x%" PRIXPTR " x22=0x%" PRIXPTR " x23=0x%" PRIXPTR "\n"
		"x24=0x%" PRIXPTR " x25=0x%" PRIXPTR " x26=0x%" PRIXPTR " x27=0x%" PRIXPTR "\n"
		"x28=0x%" PRIXPTR " fp=0x%" PRIXPTR "\n",
		(uintptr_t)signal_mcontext->regs[0], (uintptr_t)signal_mcontext->regs[1],
		(uintptr_t)signal_mcontext->regs[2], (uintptr_t)signal_mcontext->regs[3],
		(uintptr_t)signal_mcontext->regs[4], (uintptr_t)signal_mcontext->regs[5],
		(uintptr_t)signal_mcontext->regs[6], (uintptr_t)signal_mcontext->regs[7],
		(uintptr_t)signal_mcontext->regs[8], (uintptr_t)signal_mcontext->regs[9],
		(uintptr_t)signal_mcontext->regs[10], (uintptr_t)signal_mcontext->regs[11],
		(uintptr_t)signal_mcontext->regs[12], (uintptr_t)signal_mcontext->regs[13],
		(uintptr_t)signal_mcontext->regs[14], (uintptr_t)signal_mcontext->regs[15],
		(uintptr_t)signal_mcontext->regs[16], (uintptr_t)signal_mcontext->regs[17],
		(uintptr_t)signal_mcontext->regs[18], (uintptr_t)signal_mcontext->regs[19],
		(uintptr_t)signal_mcontext->regs[20], (uintptr_t)signal_mcontext->regs[21],
		(uintptr_t)signal_mcontext->regs[22], (uintptr_t)signal_mcontext->regs[23],
		(uintptr_t)signal_mcontext->regs[24], (uintptr_t)signal_mcontext->regs[25],
		(uintptr_t)signal_mcontext->regs[26], (uintptr_t)signal_mcontext->regs[27],
		(uintptr_t)signal_mcontext->regs[28], (uintptr_t)signal_mcontext->regs[29]);
	Log(message);
	Log("pc: ");
	printPC( (void*)signal_mcontext->pc );
	Log("lr: ");
	printPC( (void*)signal_mcontext->regs[30] );

	// FP-walk from the FAULTING thread's registers. _Unwind_Backtrace below
	// unwinds the handler's own alternate stack (CrashHandler -> sigchain ->
	// vdso) and never sees the crashed call stack, so the frame-pointer chain
	// is the only walk that reaches the real frames.
	Log("fp-walk: frame-pointer chain from faulting context\n");
	UnwindByFramePointer( (uintptr_t)signal_mcontext->regs[29], (uintptr_t)signal_mcontext->sp );

	// Belt and braces: scan the faulting stack for values that land inside a
	// loaded library's .text - every live return address looks like that.
	{
		uintptr_t stackTop = (uintptr_t)signal_mcontext->sp;
		uintptr_t stackLimit = stackTop + 0x20000; // fallback: 128KB
		pthread_attr_t attr;
		if ( pthread_getattr_np( pthread_self(), &attr ) == 0 )
		{
			void *stkaddr = NULL;
			size_t stksize = 0;
			pthread_attr_getstack( &attr, &stkaddr, &stksize );
			pthread_attr_destroy( &attr );
			if ( stkaddr && stksize )
				stackLimit = (uintptr_t)stkaddr + stksize;
		}
		Log("stack-scan: code pointers in the faulting stack\n");
		int found = 0;
		for ( uintptr_t a = stackTop & ~(uintptr_t)7; a + 8 <= stackLimit && found < 128; a += 8 )
		{
			uintptr_t val = *(const volatile uintptr_t *)a;
			if ( val < 0x1000 )
				continue;
			Dl_info info;
			if ( dladdr( (void *)(val - 4), &info ) <= 0 || !info.dli_fname )
				continue;
			uintptr_t base = (uintptr_t)info.dli_fbase;
			if ( val <= base + 0x1000 ) // skip PLT/thunk region
				continue;
			char smsg[512];
			snprintf( smsg, sizeof( smsg ), "STK: +0x%" PRIXPTR " (%s)\n", val - base, info.dli_fname );
			Log( smsg );
			found++;
		}
		if ( found == 0 )
			Log( "STK: no code pointers found\n" );
	}

	// Doesn't work good on armv7a
	static backtrace_t bt;
	bt.count = 0;

	// Frames are printed eagerly inside the callback, so a nested fault in
	// the unwinder still leaves us with a partial backtrace.
	_Unwind_Backtrace(UnwindBacktraceCallback, &bt);
#else
	(void)signal_mcontext;

	// Initialize unw_context and unw_cursor.
	unw_context_t unw_context = {};
	unw_getcontext(&unw_context);
	unw_cursor_t  unw_cursor = {};
	unw_init_local(&unw_cursor, &unw_context);

	while (unw_step(&unw_cursor) > 0) {
		unw_word_t ip = 0;
		unw_get_reg(&unw_cursor, UNW_REG_IP, &ip);
		printPC( (void*)ip );
	}
#endif

	Log(">>> crash report end\n");

	if (old_sa.sa_sigaction)
		(*old_sa.sa_sigaction)(sig, si, uc);
	else if(old_sa.sa_handler)
		(*old_sa.sa_handler)(sig);
}

// SA_ONSTACK is useless without an actual alternate stack: on a stack
// overflow the handler would fault again before printing anything and the
// process dies silently. Note sigaltstack() only applies to the calling
// (main) thread.
static char s_crashAltStack[256 * 1024];

void InitCrashHandler()
{
	stack_t ss;
	ss.ss_sp = s_crashAltStack;
	ss.ss_size = sizeof( s_crashAltStack );
	ss.ss_flags = 0;
	sigaltstack( &ss, NULL );

	struct sigaction act;
	act.sa_sigaction = CrashHandler;
	act.sa_flags = SA_SIGINFO | SA_ONSTACK;
	sigaction(SIGSEGV, &act, &old_sa);
	sigaction(SIGABRT, &act, &old_sa);
	sigaction(SIGBUS, &act, &old_sa);
	sigaction(SIGFPE, &act, &old_sa);
	sigaction(SIGTRAP, &act, &old_sa);
	sigaction(SIGILL, &act, &old_sa);
	sigaction(SIGSYS, &act, &old_sa);
}
