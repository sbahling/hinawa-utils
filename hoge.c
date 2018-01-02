#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <errno.h>
#include <string.h>

#include <libhinawa/fw_unit.h>
#include <libhinawa/fw_req.h>

struct region_datum {
	guint64 addr;
	guint32 size;
} __attribute__((packed));

struct region_data {
	struct region_datum a;
	struct region_datum b;
	struct region_datum c;
	struct region_datum d;
} __attribute__((packed));

static void read_region_a(HinawaFwUnit *unit, HinawaFwReq *req,
			  const struct region_datum *datum, GError **exception)
{
	guint64 addr, end;
	GArray *frames;
	int i;

	printf("Region A:\n");

	addr = datum->addr + 68;
	frames = g_array_sized_new(FALSE, TRUE, sizeof(guint32), 3);
	hinawa_fw_req_read(req, unit, addr, frames, 3, exception);
	if (*exception)
		goto end;
	end = addr + g_array_index(frames, guint32, 2);

	addr = datum->addr + g_array_index(frames, guint32, 1);
	g_array_set_size(frames, 5);
	hinawa_fw_req_read(req, unit, addr, frames, 5, exception);
	if (*exception)
		goto end;
	printf("%016lx:\n", addr);
	for (i = 0; i < 5; ++i)
		printf("    %02d: %08x\n", i, g_array_index(frames, guint32, i));
	addr += 20;

	while (addr < end) {
		int size;
		g_array_set_size(frames, 2);
		hinawa_fw_req_read(req, unit, addr, frames, 2, exception);
		if (*exception)
			goto end;
		size = g_array_index(frames, guint32, 0) & 0xffff;
		if (size == 0)
			break;
		addr += 8;

		for (i = 0; i < 2; ++i)
			printf("  %08x\n", g_array_index(frames, guint32, i));

		g_array_set_size(frames, size / 4);
		hinawa_fw_req_read(req, unit, addr, frames, size / 4, exception);
		if (*exception)
			goto end;
		for (i = 0; i < size / 4; ++i)
			printf("    %02d: %08x\n",
			       i, g_array_index(frames, guint32, i));
		addr += size;
	}
end:
	g_array_free(frames, TRUE);
}

struct region_b_section_end {
	guint64 first;
	guint64 second;
	guint64 third;
	guint64 fourth;
};

static void read_b_1st_section(HinawaFwUnit *unit, HinawaFwReq *req,
			       guint64 base, guint64 end, GError **exception)
{
	guint64 addr = base;
	GArray *frames;
	unsigned int entries;

	frames = g_array_sized_new(FALSE, TRUE, sizeof(guint32), 1);
	hinawa_fw_req_read(req, unit, addr, frames, 1, exception);
	if (*exception)
		goto end;
	entries = g_array_index(frames, guint32, 0);
	addr += 4;

	for (int i = 0; i < entries; ++i) {
		unsigned int size;
		guint64 label_addr;

		hinawa_fw_req_read(req, unit, addr, frames, 1, exception);
		if (*exception)
			goto end;
		label_addr = 0xffffe0000000 + g_array_index(frames, guint32, 0);

		/* TODO: retrieve a label. */
		printf("    entry %d: (%016lx)\n", i, addr);

		addr += 4;

		for (int j = 0; j < 5; ++j) {
			printf("      param: %02d\n", j);

			hinawa_fw_req_read(req, unit, addr, frames, 1,
					   exception);
			if (*exception)
				goto end;
			size = g_array_index(frames, guint32, 0);
			addr += 4;

			g_array_set_size(frames, size / 4);
			hinawa_fw_req_read(req, unit, addr, frames, size / 4,
					   exception);
			if (*exception)
				goto end;

			for (int k = 0; k < size / 4; ++k)
				printf("        %02d: %08x\n",
				       k, g_array_index(frames, guint32, k));
			addr += size;
		}
	}
end:
	g_array_free(frames, TRUE);
}

static void read_b_2nd_section(HinawaFwUnit *unit, HinawaFwReq *req,
			       guint64 base, guint64 end, GError **exception)
{
	guint64 addr;
	unsigned int entries;
	GArray *frames;

	frames = g_array_sized_new(FALSE, TRUE, sizeof(guint32), 12);
	entries = (end - base) / 48;
	addr = base;

	for (int i = 0; i < entries; ++i) {
		g_array_set_size(frames, 12);
		hinawa_fw_req_read(req, unit, addr, frames, 12, exception);
		if (*exception)
			goto end;
		printf("    entry: %02d 0x%016lx\n", i, addr);
		for (int j = 0; j < 12; ++j) {
			printf("      %02d: %08x\n",
			       j, g_array_index(frames, guint32, j));
		}
		addr += 48;
	}
end:
	g_array_free(frames, TRUE);
}

static void read_b_3rd_section(HinawaFwUnit *unit, HinawaFwReq *req,
			       guint64 base, guint64 end, GError **exception)
{
	guint64 addr;
	unsigned int entries;
	GArray *frames;

	frames = g_array_sized_new(FALSE, TRUE, sizeof(guint32), 7);
	entries = (end - base) / 28;
	addr = base;

	for (int i = 0; i < entries; ++i) {
		g_array_set_size(frames, 7);
		hinawa_fw_req_read(req, unit, addr, frames, 7, exception);
		if (*exception)
			goto end;
		if (g_array_index(frames, guint32, 0) == 0x00000000)
			break;

		printf("    entry: %02d (0x%016lx)\n", i, addr);

		for (int j = 0; j < 7; ++j)
			printf("      %02d: %08x\n",
			       j, g_array_index(frames, guint32, j));
		addr += 28;
	}
end:
	g_array_free(frames, TRUE);
}

static void read_b_4th_section(HinawaFwUnit *unit, HinawaFwReq *req,
			       guint64 base, guint64 end, GError **exception)
{
	guint64 addr;
	GArray *frames;
	unsigned int count;

	addr = base;
	frames = g_array_sized_new(FALSE, TRUE, sizeof(guint32), 6);

	count = 0;
	while (addr < end) {
		hinawa_fw_req_read(req, unit, addr, frames, 6, exception);
		if (*exception)
			goto end;
		if (g_array_index(frames, guint32, 0) == 0x00000000)
			break;
		addr += 24;

		printf("    entry %02d\n", count);
		for (int j = 0; j < 6; ++j)
			printf("      %02d: %08x\n",
			       j, g_array_index(frames, guint32, j));
		count += 1;
	}
end:
	g_array_free(frames, TRUE);
}

static void read_region_b(HinawaFwUnit *unit, HinawaFwReq *req,
			  const struct region_datum *datum, GError **exception)
{
	struct region_b_section_end section_end;
	guint64 addr;
	GArray *frames;

	printf("Region B:\n");

	addr = datum->addr;
	frames = g_array_sized_new(FALSE, TRUE, sizeof(guint32), 4);
	hinawa_fw_req_read(req, unit, addr, frames, 4, exception);
	if (*exception)
		goto end;
	addr += 16;

	printf("  Sections:\n");
	section_end.first = datum->addr + g_array_index(frames, guint32, 0);
	section_end.second = datum->addr + g_array_index(frames, guint32, 1);
	section_end.third = datum->addr + g_array_index(frames, guint32, 2);
	section_end.fourth = datum->addr + g_array_index(frames, guint32, 3);

	printf("    1: %016lx\n", section_end.first);
	printf("    2: %016lx\n", section_end.second);
	printf("    3: %016lx\n", section_end.third);
	printf("    4: %016lx\n", section_end.fourth);

	printf("  section 1:\n");
	read_b_1st_section(unit, req, addr, section_end.first, exception);
	if (*exception)
		goto end;

	printf("  section 2:\n");
	read_b_2nd_section(unit, req, section_end.first, section_end.second,
			   exception);
	if (*exception)
		goto end;

	printf("  section 3:\n");
	read_b_3rd_section(unit, req, section_end.second, section_end.third,
			   exception);
	if (*exception)
		goto end;

	printf("  section 4:\n");
	read_b_4th_section(unit, req, section_end.third, section_end.fourth,
			   exception);
	if (*exception)
		goto end;
end:
	g_array_free(frames, TRUE);
}

static void read_region_c(HinawaFwUnit *unit, HinawaFwReq *req,
			  const struct region_datum *datum, GError **exception)
{
	guint64 addr;
	GArray *frames;
	int i;

	printf("Region C:\n");

	addr = datum->addr + 8;
	frames = g_array_sized_new(FALSE, TRUE, sizeof(guint32), 7);
	hinawa_fw_req_read(req, unit, addr, frames, 7, exception);
	if (*exception)
		goto end;
	for (i = 0; i < 7; ++i)
		printf("  %02d: %08x\n", i, g_array_index(frames, guint32, i));

	addr += 28;
	g_array_set_size(frames, 8);
	hinawa_fw_req_read(req, unit, addr, frames, 8, exception);
	if (*exception)
		goto end;

	addr += 36;
	g_array_set_size(frames, 8);
	hinawa_fw_req_read(req, unit, addr, frames, 8, exception);
	if (*exception)
		goto end;
end:
	g_array_free(frames, TRUE);
}

static void read_region_d(HinawaFwUnit *unit, HinawaFwReq *req,
			  const struct region_datum *datum, GError **exception)
{
	guint64 addr;
	GArray *frames;
	unsigned int count;

	addr = datum->addr;
	frames = g_array_sized_new(FALSE, TRUE, sizeof(guint32), 8);
	hinawa_fw_req_read(req, unit, addr, frames, 1, exception);
	if (*exception)
		goto end;
	count = g_array_index(frames, guint32, 0);
	addr += 4;

	printf("Region D:\n");
	for (int i = 0; i < count; ++i) {
		addr += i * 4 * 5;
		hinawa_fw_req_read(req, unit, addr, frames, 5, exception);
		if (*exception)
			goto end;
		printf("  entry %02d: %016lx\n", i, addr);
		for (int j = 0; j < 5; ++j) {
			printf("    %02d: %08x\n",
			       j, g_array_index(frames, guint32, j));
		}
	}
end:
	g_array_free(frames, TRUE);
}

static void read_registers(HinawaFwUnit *unit, GError **exception)
{
	struct region_data regions;
	HinawaFwReq *req;
	GArray *frames;

	req = g_object_new(HINAWA_TYPE_FW_REQ, "timeout", 1000, NULL);
	frames = g_array_sized_new(FALSE, TRUE, sizeof(guint32), 8);

	hinawa_fw_req_read(req, unit, 0xffffe0000000, frames, 8, exception);
	if (*exception)
		goto end;

	regions.a.addr = 0xffffe0000000 + g_array_index(frames, guint32, 0);
	regions.a.size = g_array_index(frames, guint32, 1);
	regions.b.addr = 0xffffe0000000 + g_array_index(frames, guint32, 2);
	regions.b.size = g_array_index(frames, guint32, 3);
	regions.c.addr = 0xffffe0000000 + g_array_index(frames, guint32, 4);
	regions.c.size = g_array_index(frames, guint32, 5);
	regions.d.addr = 0xffffe0000000 + g_array_index(frames, guint32, 6);
	regions.d.size = g_array_index(frames, guint32, 7);

	printf("A: %016lx: %d\n", regions.a.addr, regions.a.size);
	printf("B: %016lx: %d\n", regions.b.addr, regions.b.size);
	printf("C: %016lx: %d\n", regions.c.addr, regions.c.size);
	printf("D: %016lx: %d\n", regions.d.addr, regions.d.size);

	read_region_a(unit, req, &regions.a, exception);
	if (*exception)
		goto end;
	read_region_b(unit, req, &regions.b, exception);
	if (*exception)
		goto end;
	read_region_c(unit, req, &regions.c, exception);
	if (*exception)
		goto end;
	read_region_d(unit, req, &regions.d, exception);
end:
	g_array_free(frames, TRUE);
	g_clear_object(&req);
}

int main(int argc, char *argv[])
{
	HinawaFwUnit *unit;
	GError *exception = NULL;

	unit = g_object_new(HINAWA_TYPE_FW_UNIT, NULL);
	hinawa_fw_unit_open(unit, argv[1], &exception);
	if (exception)
		goto end;

	hinawa_fw_unit_listen(unit, &exception);
	if (exception)
		goto end;

	read_registers(unit, &exception);
	if (exception)
		goto end;
end:
	hinawa_fw_unit_unlisten(unit);
	g_clear_object(&unit);

	if (exception) {
		printf("%s: %s\n",
		       g_quark_to_string(exception->domain), exception->message);
		g_clear_error(&exception);
	}

	return EXIT_SUCCESS;
}
