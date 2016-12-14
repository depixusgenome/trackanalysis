#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include "legacy/legacygr.h"
namespace legacy { namespace { // unitset
    long    counter = 0, n_error = 0;
    float   abslow, dx;     /* offset and scale for automatic abscissas */
    int     absf;           /* flag for automatic abscissas */
    int     sizef = 0;          /* flag for changing plot size */
    int     aflag = 0;
    char    plt_data_path[512];
    # define BUILD_COLOR(r,g,b)		(((b)&0xff)<<16)+(((g)&0xff)<<8)+((r)&0xff)
    int	Black			=	0;
    int	Blue			= BUILD_COLOR(  0,  0,128); 
    int	Green			= BUILD_COLOR(  0,128,  0);
    int	Cyan			= BUILD_COLOR(  0,128,128);
    int	Red				= BUILD_COLOR(128,  0,  0);
    int	Magenta			= BUILD_COLOR(128,  0,128);
    int	Brown			= BUILD_COLOR(128,128,  0);
    int	Lightgray		= BUILD_COLOR(171,171,171);
    int	Darkgray		= BUILD_COLOR( 85, 85, 85);
    int	Lightblue		= BUILD_COLOR( 64, 64,255);
    int	Lightgreen		= BUILD_COLOR( 64,255, 64);
    int	Lightcyan		= BUILD_COLOR(  0,255,255);
    int	Lightred		= BUILD_COLOR(255, 64, 64);
    int	Lightmagenta	= BUILD_COLOR(255,  0,255);
    int	Yellow			= BUILD_COLOR(255,255,  0);
    int	White 			= BUILD_COLOR(255,255,255);

    # define B_LINE 	65536
    # define MAX_ERROR 	20
    # define OP_SIZE 	32
    # define CRT_Z 		26
    # define GR_SIZE	16384
    # define Mystrdup(src)	((src) == NULL) ? NULL : strdup((src))
    # define    X_AXIS      2304    /* 2048 + 256 */
    # define    Y_AXIS      2048
    char    *Mystrdupre(char *dest, const  char *src)
    {
        if (dest != NULL)
        {
            free(dest);
        }

        if (src != NULL && strlen(src) > 0)
        {
            dest = strdup(src);
        }
        else
        {
            dest = NULL;
        }

        return dest;
    }

    # define MAX_DATA 		16
    # define NOAXES		0000002
    # define AXES_PRIME	0000400
    # define TRIM		0001000
    # define XLOG		0002000
    # define YLOG		0004000
    # define CROSS		0020000
    
    # define GRID		TRIM + NOAXES + AXES_PRIME
    
    # define X_NUM		0000001
    # define Y_NUM		0000002
    # define X_LIM		0000004			/* axis limit is not imposed */
    # define Y_LIM		0000010
    
    # define 	IS_SPECIAL		32
    # define 	IS_DATA_SET		2048
    # define 	IS_PLOT_LABEL		4096
    # define 	IS_X_UNIT_SET		16
    # define 	IS_Y_UNIT_SET		17
    # define 	IS_T_UNIT_SET		19
    
    # define 	ABS_COORD		0
    # define 	USR_COORD		1
    # define 	VERT_LABEL_USR		2
    # define 	VERT_LABEL_ABS		3
    
    # define 	IS_TERRA		12
    # define 	IS_GIGA			9
    # define 	IS_MEGA			6
    # define 	IS_KILO			3
    # define 	IS_MILLI		-3
    # define 	IS_MICRO		-6
    # define 	IS_NANO			-9
    # define 	IS_PICO			-12
    # define 	IS_FEMTO		-15
    
    # define 	IS_VOLT			256
    # define 	IS_AMPERE		512
    # define 	IS_METER		1024
    # define 	IS_NEWTON		2048
    # define 	IS_SECOND		4096
    # define 	IS_GRAMME		8192
    # define 	IS_GAUSS		16384
    # define 	IS_OHM			32768
    # define 	IS_RAW_U		-128 		/* raw data */

    struct unit_set
    {
        int type, sub_type, axis;	/* identifier */
        float ax, dx;			/* the offset and increment */
        char	decade;			/* the decade value*/
        char	mode;			/* log or a^2 */
        char *name;			/* the text of it */
    };

    unit_set *build_unit_set(int type, float ax, float dx, char decade, char mode, char *name)
    {
        unit_set *uns;
        
        uns = (unit_set*)calloc(1,sizeof(unit_set));
        if ( uns == NULL )		return NULL;
        uns->type = type;
        uns->ax = ax;
        uns->dx = dx;
        uns->decade = decade;
        uns->mode = mode;
        if (name == NULL)      uns->name = NULL;
        else if (name != NULL && strncmp(name,"no_name",7) == 0 ) 
          uns->name = NULL;
        else	uns->name = Mystrdup(name);
        return uns;
    }

    int 	free_unit_set(unit_set *uns)
    {
        if (uns == NULL)	return 1;
        if (uns->name != NULL) 	free(uns->name);
        free(uns);	uns = NULL;
        return 0;
    }

    int	unit_to_type(char *unit, int *type, int *decade)
    {
        register int t, d;
        int adv = 1;
        
        if (unit == NULL)	return 1;
        if (strncmp(unit,"\\mu ",4) == 0 )	
        {
            d = IS_MICRO;
            unit += 4;
        }
        else
        {
            switch (unit[0])
            {
                case 'T'  :		d = IS_TERRA;		break;
                case 'G' :		d = IS_GIGA;		break;
                case 'M' :		d = IS_MEGA;		break;
                case 'K' :		d = IS_KILO;		break;
                case 'm' :		d = IS_MILLI;		break;
                case 'n' : 		d = IS_NANO;		break;
                case 'p' :		d = IS_PICO;		break;
                case 'f' :		d = IS_FEMTO;		break;
                default :		adv = 0;	d = 0;	break;
            };
            unit += adv;
        }
        if (strncmp(unit,"\\Omega ",6 )== 0 )	
        {
            t = IS_OHM;
        }	
        else
        {
            switch (unit[0])
            {
                case 'V' :	t = IS_VOLT;		break;
                case 'A' :	t = IS_AMPERE;		break;
                case 'm' :	t = IS_METER;		break;
                case 'N' :	t = IS_NEWTON;		break;
                case 's' :	t = IS_SECOND;		break;
                case 'g' :	t = IS_GRAMME;		break;
                case 'G' :	t = IS_GAUSS;		break;
                default :	return 1;		break;
            };
        }
        *type = t;
        *decade = d;
        return 0;
    }
}}

namespace legacy { namespace { // ds
    struct ErrorInFile {};
    char const * Out_Of_Memory = nullptr;
    char const * Wrong_Argument = nullptr;
    [[noreturn]] void xvin_ptr_error(char const *) { throw ErrorInFile(); }
    [[noreturn]] void error_in_file( char *, ...) { throw ErrorInFile(); }

    int     *data_color;
    int     max_data_color;
    /*
# include "color.h"
    int     data_color[] = {Yellow, Lightgreen, Lightred, Lightblue};
    int     max_data_color = 4;
    */

    struct plot_label
    {
        int type;			/* absolute or user defined */
        float xla, yla;			/* the position of label */
        char *text;			/* the text of it */
        struct box *b;			/* the plot box */
    };

    struct data_set
    {
        int nx, ny, type;		/* number of x and y data */
        int mx, my;			/* size alloc for x and y */
        float *xd, *yd;			/* the x and y data */
        float *xe, *ye;			/* the x and y error on data, symetric if xeb and yev are not defined, error above xd otherwise, (max value for boxplot)*/
        // TODO EXPORT DATA IN GR
        float *xed, *yed;       /* the x and y error on data, below the point (min value for boxplot)*/
        float *xbu, *ybu;   /* the x and y upperside of the box for boxplot, if xbd and ybd is not define, the box will be symetric */
        float *xbd, *ybd;    /* the x and y downside of the box for boxplot */
        float boxplot_width;
        // END TODO
        char *symb;			/* the symbol to plot */
        int m;				/* the line style */
        int color;			/* the drawing color */
        time_t time;			/* date of creation */ /* long int changed into time_t 2006/11/10, NG */
        char *source;
        char *history;
        char *treatement;
        char **special;
        int n_special, m_special;
        struct plot_label **lab;	/* labelling in the plot attached to ds */
        int n_lab, m_lab;		/* the last and size*/
        int need_to_refresh;
        double record_duration;         /* duration of data acquisition in micro seconds */
        long long recordata_settart;         /* start of duration of data */
        int invisible;                  /* if set make the dataset invisible, but data is still there */
        int user_ispare[16];
        float user_fspare[16];
        float src_parameter[8];        // numerical value of parameter characterizing data (ex. temperature ...)
        char *src_parameter_type[8];   // the description of these parameters
    };

    int free_data_set(data_set *ds)
    {
        int i;

        if (ds == NULL)
        {
            return 1;
        }

        if (ds->xd != NULL)
        {
            free(ds->xd);
            ds->xd = NULL;
        }

        if (ds->yd != NULL)
        {
            free(ds->yd);
            ds->yd = NULL;
        }

        if (ds->xe != NULL)
        {
            free(ds->xe);
            ds->xe = NULL;
        }

        if (ds->ye != NULL)
        {
            free(ds->ye);
            ds->ye = NULL;
        }

        if (ds->xed != NULL)
        {
            free(ds->xed);
            ds->xed = NULL;
        }

        if (ds->yed != NULL)
        {
            free(ds->yed);
            ds->yed = NULL;
        }

        if (ds->xbu != NULL)
        {
            free(ds->xbu);
            ds->xbu = NULL;
        }

        if (ds->ybu != NULL)
        {
            free(ds->ybu);
            ds->yed = NULL;
        }

        if (ds->xbd != NULL)
        {
            free(ds->xbd);
            ds->xbd = NULL;
        }

        if (ds->ybd != NULL)
        {
            free(ds->ybd);
            ds->ybd = NULL;
        }

        if (ds->symb != NULL)
        {
            free(ds->symb);
            ds->symb = NULL;
        }

        if (ds->source != NULL)
        {
            free(ds->source);
            ds->source = NULL;
        }

        if (ds->history != NULL)
        {
            free(ds->history);
            ds->history = NULL;
        }

        if (ds->treatement != NULL)
        {
            free(ds->treatement);
            ds->treatement = NULL;
        }

        if (ds->special != NULL)
        {
            for (i = 0 ; i < ds->n_special ; i++)
                if (ds->special[i] != NULL)
                {
                    free(ds->special[i]);
                    ds->special[i] = NULL;
                }

            free(ds->special);
            ds->special = NULL;
        }

        for (i = 0 ; i < ds->n_lab ; i++)
        {
            if (ds->lab[i]->text != NULL)
            {
                free(ds->lab[i]->text);
                ds->lab[i]->text = NULL;
            }

            if (ds->lab[i] != NULL)
            {
                free(ds->lab[i]);
                ds->lab[i] = NULL;
            }
        }

        if (ds->lab)
        {
            free(ds->lab);
            ds->lab = NULL;
        }

        for (i = 0 ; i < 8 ; i++)
        {
            if (ds->src_parameter_type[i] != NULL)
            {
                free(ds->src_parameter_type[i]);
                ds->src_parameter_type[i] = NULL;
            }
        }

        free(ds);
        ds = NULL;
        return 0;
    }

    int add_to_data_set(data_set *ds, int type, void *stuff)
    {
        if (stuff == NULL || ds == NULL)
        {
            xvin_ptr_error(Wrong_Argument);
        }
        else if (type == IS_SPECIAL && strlen((char *)stuff) > 0)
        {
            if (ds->n_special >=  ds->m_special)
            {
                ds->m_special++;
                ds->special = (char **)realloc
                              (ds->special, ds->m_special * sizeof(char *));

                if (ds->special == NULL)
                {
                    xvin_ptr_error(Out_Of_Memory);
                }
            }

            ds->special[ds->n_special] = strdup((char *)stuff);
            ds->n_special++;
        }
        else if (type == IS_PLOT_LABEL)
        {
            if (ds->n_lab >= ds->m_lab)
            {
                ds->m_lab += MAX_DATA;
                ds->lab = (plot_label **)realloc(ds->lab, ds->m_lab * sizeof(plot_label *));

                if (ds->lab == NULL)
                {
                    xvin_ptr_error(Out_Of_Memory);
                }
            }

            if (((plot_label *)stuff)->text != NULL)   /* no empty label */
            {
                ds->lab[ds->n_lab] = (plot_label *)stuff;
                ds->n_lab++;
            }

            ds->need_to_refresh = 1;
        }

        return 0;
    }

    data_set *build_data_set(int nx, int ny)
    {
        int i;
        data_set *ds;

        if (nx <= 0 || ny <= 0)
        {
            return NULL;
        }

        ds = (data_set *)calloc(1, sizeof(data_set));

        if (ds == NULL)
        {
            xvin_ptr_error(Out_Of_Memory);
        }

        ds->xd = (float *)calloc(nx, sizeof(float));
        ds->yd = (float *)calloc(ny, sizeof(float));

        if (ds->xd == NULL || ds->yd == NULL)
        {
            free_data_set(ds);
            xvin_ptr_error(Out_Of_Memory);
        }

        ds->mx = nx;
        ds->my = ny;
        ds->m = 1;
        ds->xe = ds->ye = NULL;
        ds->xed = ds->yed = NULL;
        ds->xbu = ds->ybu = NULL;
        ds->xbd = ds->ybd = NULL;
        ds->color = 1;
        ds->n_special = ds->m_special = 0;
        ds->special = NULL;
        ds->symb = NULL;
        ds->source = NULL;
        ds->history = NULL;
        ds->treatement = NULL;
        ds->special = NULL;
        ds->lab = (plot_label **)calloc(MAX_DATA, sizeof(plot_label *));
        ds->boxplot_width = 1;

        if (ds->lab == NULL)
        {
            free_data_set(ds);
            xvin_ptr_error(Out_Of_Memory);
        }

        ds->m_lab = MAX_DATA;
        // following line added 2007/10/16, N.G.:
        ds->nx = nx;
        ds->ny = ny;

        for (i = 0 ; i < 8 ; i++)
        {
            ds->src_parameter_type[i] = NULL;
            ds->src_parameter[i] = 0;
        }

        ds->invisible = 0;
        return ds;
    }

    data_set *build_adjust_data_set(data_set *ds, int nx, int ny)
    {
        if (ds == NULL || nx <= 0 || ny <= 0)
        {
            return (build_data_set(nx, ny));
        }

        if (nx < ds->mx || ny < ds->my)
        {
            ds->nx = nx;
            ds->ny  = ny;
            return ds;
        }

        ds->xd = (float *)realloc(ds->xd, nx * sizeof(float));
        ds->yd = (float *)realloc(ds->yd, ny * sizeof(float));

        if (ds->xd == NULL || ds->yd == NULL)
        {
            xvin_ptr_error(Out_Of_Memory);
        }

        ds->mx = nx;
        ds->my = ny;

        if (ds->xe != NULL)
        {
            ds->xe = (float *)realloc(ds->xe, nx * sizeof(float));

            if (ds->xe == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (ds->ye != NULL)
        {
            ds->ye = (float *)realloc(ds->ye, ny * sizeof(float));

            if (ds->ye == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (ds->xed != NULL)
        {
            ds->xed = (float *)realloc(ds->xed, nx * sizeof(float));

            if (ds->xed == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (ds->yed != NULL)
        {
            ds->yed = (float *)realloc(ds->yed, ny * sizeof(float));

            if (ds->yed == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (ds->xbu != NULL)
        {
            ds->xbu = (float *)realloc(ds->xbu, nx * sizeof(float));

            if (ds->xbu == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (ds->ybu != NULL)
        {
            ds->ybu = (float *)realloc(ds->ybu, ny * sizeof(float));

            if (ds->ybu == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (ds->xbd != NULL)
        {
            ds->xbd = (float *)realloc(ds->xbd, nx * sizeof(float));

            if (ds->xbd == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (ds->ybd != NULL)
        {
            ds->ybd = (float *)realloc(ds->ybd, ny * sizeof(float));

            if (ds->ybd == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        return ds;
    }

    data_set *alloc_data_set_y_error(data_set *ds)
    {
        if (ds == NULL)
        {
            xvin_ptr_error(Wrong_Argument);
        }

        if (ds->ye != NULL)
        {
            return ds;
        }

        ds->ye = (float *)calloc(ds->my, sizeof(float));

        if (ds->ye == NULL)
        {
            xvin_ptr_error(Out_Of_Memory);
        }

        return ds;
    }

    data_set *alloc_data_set_x_error(data_set *ds)
    {
        if (ds == NULL)
        {
            xvin_ptr_error(Wrong_Argument);
        }

        if (ds->xe != NULL)
        {
            return ds;
        }

        ds->xe = (float *)calloc(ds->mx, sizeof(float));

        if (ds->xe == NULL)
        {
            xvin_ptr_error(Out_Of_Memory);
        }

        return ds;
    }

    data_set *duplicate_data_set(const data_set *src, data_set *dest)
    {
        int i, j;
        plot_label *sp, *dp;
        int n_min, m_min;

        if (src == NULL)
        {
            xvin_ptr_error(Wrong_Argument);
        }

        n_min = (src->nx < src->ny) ? src->nx : src->ny;
        m_min = (src->mx < src->my) ? src->mx : src->my;
        m_min = (m_min <= 0) ? 16 : m_min;

        if ((dest == NULL) || (dest->mx < n_min) || (dest->my < n_min))
        {
            if (n_min > 0)
            {
                dest = build_adjust_data_set(dest, n_min, n_min);
            }
            else
            {
                dest = build_adjust_data_set(dest, m_min, m_min);

                if (dest != NULL)
                {
                    dest->nx = dest->ny = n_min;
                }
            }

            if (dest == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (src->xe != NULL && dest->xe == NULL)
        {
            if (src->nx > 0)
            {
                dest->xe = (float *)realloc(dest->xe, src->nx * sizeof(float));
            }
            else
            {
                dest->xe = (float *)realloc(dest->xe, m_min * sizeof(float));
            }

            if (dest->xe == NULL)
            {
                free_data_set(dest);
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (src->ye != NULL && dest->ye == NULL)
        {
            if (src->ny > 0)
            {
                dest->ye = (float *)realloc(dest->ye, src->ny * sizeof(float));
            }
            else
            {
                dest->ye = (float *)realloc(dest->ye, m_min * sizeof(float));
            }

            if (dest->ye == NULL)
            {
                free_data_set(dest);
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (src->xed != NULL && dest->xed == NULL)
        {
            if (src->nx > 0)
            {
                dest->xed = (float *)realloc(dest->xed, src->nx * sizeof(float));
            }
            else
            {
                dest->xed = (float *)realloc(dest->xed, m_min * sizeof(float));
            }

            if (dest->xed == NULL)
            {
                free_data_set(dest);
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (src->yed != NULL && dest->yed == NULL)
        {
            if (src->ny > 0)
            {
                dest->yed = (float *)realloc(dest->yed, src->ny * sizeof(float));
            }
            else
            {
                dest->yed = (float *)realloc(dest->yed, m_min * sizeof(float));
            }

            if (dest->yed == NULL)
            {
                free_data_set(dest);
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (src->xbu != NULL && dest->xbu == NULL)
        {
            if (src->nx > 0)
            {
                dest->xbu = (float *)realloc(dest->xbu, src->nx * sizeof(float));
            }
            else
            {
                dest->xbu = (float *)realloc(dest->xbu, m_min * sizeof(float));
            }

            if (dest->xbu == NULL)
            {
                free_data_set(dest);
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (src->ybu != NULL && dest->ybu == NULL)
        {
            if (src->ny > 0)
            {
                dest->ybu = (float *)realloc(dest->ybu, src->ny * sizeof(float));
            }
            else
            {
                dest->ybu = (float *)realloc(dest->ybu, m_min * sizeof(float));
            }

            if (dest->ybu == NULL)
            {
                free_data_set(dest);
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (src->xbd != NULL && dest->xbd == NULL)
        {
            if (src->nx > 0)
            {
                dest->xbd = (float *)realloc(dest->xbd, src->nx * sizeof(float));
            }
            else
            {
                dest->xbd = (float *)realloc(dest->xbd, m_min * sizeof(float));
            }

            if (dest->xbd == NULL)
            {
                free_data_set(dest);
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (src->ybd != NULL && dest->ybd == NULL)
        {
            if (src->ny > 0)
            {
                dest->ybd = (float *)realloc(dest->ybd, src->ny * sizeof(float));
            }
            else
            {
                dest->ybd = (float *)realloc(dest->ybd, m_min * sizeof(float));
            }

            if (dest->ybd == NULL)
            {
                free_data_set(dest);
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        dest->boxplot_width = src->boxplot_width;
        dest->symb = Mystrdup(src->symb);
        dest->m = src->m;
        dest->color = src->color;
        dest->time = src->time;
        dest->nx = n_min;
        dest->ny = n_min;

        for (j = 0 ; j < n_min ; j++)
        {
            dest->xd[j] = src->xd[j];
            dest->yd[j] = src->yd[j];
        }

        if (src->xe != NULL)
        {
            for (j = 0 ; j < dest->nx ; j++)
            {
                dest->xe[j] = src->xe[j];
            }
        }

        if (src->ye != NULL)
        {
            for (j = 0 ; j < dest->ny ; j++)
            {
                dest->ye[j] = src->ye[j];
            }
        }

        if (src->xed != NULL)
        {
            for (j = 0 ; j < dest->nx ; j++)
            {
                dest->xed[j] = src->xed[j];
            }
        }

        if (src->yed != NULL)
        {
            for (j = 0 ; j < dest->ny ; j++)
            {
                dest->yed[j] = src->yed[j];
            }
        }

        if (src->xbu != NULL)
        {
            for (j = 0 ; j < dest->nx ; j++)
            {
                dest->xbu[j] = src->xbu[j];
            }
        }

        if (src->ybu != NULL)
        {
            for (j = 0 ; j < dest->ny ; j++)
            {
                dest->ybu[j] = src->ybu[j];
            }
        }

        if (src->xbd != NULL)
        {
            for (j = 0 ; j < dest->nx ; j++)
            {
                dest->xbd[j] = src->xbd[j];
            }
        }

        if (src->ybd != NULL)
        {
            for (j = 0 ; j < dest->ny ; j++)
            {
                dest->ybd[j] = src->ybd[j];
            }
        }

        dest->boxplot_width = src->boxplot_width;
        dest->source = Mystrdup(src->source);
        dest->history = Mystrdup(src->history);
        dest->treatement = Mystrdup(src->treatement);

        if (src->special != NULL)
        {
            for (i = 0 ; i < src->n_special ; i++)
            {
                add_to_data_set(dest, IS_SPECIAL, (void *)(src->special[i]));
            }
        }

        for (i = 0 ; i < src->n_lab ; i++)
        {
            sp = src->lab[i];
            dp = (plot_label *)calloc(1, sizeof(plot_label));

            if (dp == NULL)
            {
                return NULL;
            }

            *dp = *sp;
            dp->text = Mystrdup(sp->text);

            if (add_to_data_set(dest, IS_PLOT_LABEL, (void *)dp))
            {
                return NULL;
            }
        }

        for (i = 0 ; i < 16 ; i++)
        {
            dest->user_ispare[i] = src->user_ispare[i];
            dest->user_fspare[i] = src->user_fspare[i];
        }
        for (i = 0 ; i < 8 ; i++)
        {
            dest->src_parameter[i] = src->src_parameter[i];

            if (src->src_parameter_type[i] != NULL && strlen(src->src_parameter_type[i]) > 0)
            {
                dest->src_parameter_type[i] = strdup(src->src_parameter_type[i]);
            }
        }

        return dest;
    }

    int push_plot_label_in_ds(data_set *ds, float tx, float ty, char *label, int type)
    {
        plot_label *pl;

        if (ds == NULL || label == NULL || strlen(label) < 1)
        {
            return 1;
        }

        pl = (plot_label *)calloc(1, sizeof(struct plot_label));

        if (pl == NULL)
        {
            fprintf(stderr, "realloc error \n");
            exit(1);
        }

        pl->xla = tx;
        pl->yla = ty;
        pl->text = (char *)strdup(label);
        pl->type = type;

        if (pl->text == NULL)
        {
            fprintf(stderr, "strdup error \n");
            return 1; //exit(1);
        }

        return add_to_data_set(ds, IS_PLOT_LABEL, (void *)pl);
    }
}}

namespace legacy { namespace {
    struct IFile
    {
        int n_line;
        char const * filename;
        FILE *fpi;
    };

    struct one_plot
    {
        int type;
        char *filename, *dir, *title, *x_title, *y_title;
        char *x_prime_title, *y_prime_title;
        char *x_prefix, *y_prefix, *t_prefix, *x_unit, *y_unit, *t_unit;
        float width, height, right, up;
        float ax, dx, ay, dy, at, dt;
        int iopt, iopt2;
        float tick_len, tick_len_x, tick_len_y;
        float x_lo, x_hi, y_lo, y_hi;
        struct data_set **dat;      /* the real data */
        int n_dat, m_dat;       /* the number of data set*/
        int cur_dat;            /* the current one */
        struct plot_label **lab;    /* labelling in the plot */
        int n_lab, m_lab;       /* the last and size*/
        unit_set    **xu;           /* x unit set */
        int n_xu, m_xu, c_xu,  c_xu_p;
        unit_set    **yu;           /* y unit set */
        int n_yu, m_yu, c_yu,  c_yu_p;
        unit_set    **tu;           /* t unit set (associated with index) */
        int n_tu, m_tu, c_tu, c_tu_p;
        int need_to_refresh;
        int data_changing;
        int transfering_data_to_box;
        int user_id;                  /* a user identifier */
        bool read_only; /* can't be removed by user interface */
        int user_ispare[16];
        float user_fspare[16];
    };

    int add_data_to_one_plot (one_plot *op, int type, void *stuff)
    {
        int i = 0;
        data_set *ds;

        if (stuff == NULL || op == NULL)
            xvin_ptr_error(Wrong_Argument);
        if (type == IS_DATA_SET)
        {
            if (op->n_dat >= op->m_dat )
            {
                op->m_dat += MAX_DATA;
                op->dat = (data_set**)realloc(op->dat,op->m_dat*sizeof(data_set*));
                if (op->dat == NULL)	xvin_ptr_error(Out_Of_Memory);
            }
            op->dat[op->n_dat] = (data_set*)stuff;
            ((data_set*)stuff)->color=data_color[(op->n_dat)%max_data_color];
            op->n_dat++;
            op->need_to_refresh = 1;
        }
        else if (type == IS_SPECIAL)
        {
            ds = op->dat[op->cur_dat];
            return add_to_data_set(ds, type, stuff);
        }
        else if (type == IS_PLOT_LABEL)
        {
            if (op->n_lab >= op->m_lab )
            {
                op->m_lab += MAX_DATA;
                op->lab = (plot_label**)realloc(op->lab,op->m_lab*sizeof(plot_label*));
                if (op->lab == NULL)	xvin_ptr_error(Out_Of_Memory);
            }
            if (((plot_label*)stuff)->text != NULL)	/* no empty label */
            {
                op->lab[op->n_lab] = (plot_label*)stuff;
                op->n_lab++;
            }
            op->need_to_refresh = 1;
        }
        else if (type == IS_X_UNIT_SET)
        {
            if (op->n_xu >= op->m_xu )
            {
                op->m_xu += MAX_DATA;
                op->xu = (unit_set**)realloc(op->xu,op->m_xu*sizeof(unit_set*));
                if (op->xu == NULL)		xvin_ptr_error(Out_Of_Memory);
            }
            op->xu[op->n_xu] = (unit_set*)stuff;
            ((unit_set*)stuff)->axis = IS_X_UNIT_SET;
            op->n_xu++;
            op->need_to_refresh = 1;
        }
        else if (type == IS_Y_UNIT_SET)
        {
            if (op->n_yu >= op->m_yu )
            {
                op->m_yu += MAX_DATA;
                op->yu = (unit_set**)realloc(op->yu,op->m_yu*sizeof(unit_set*));
                if (op->yu == NULL)		xvin_ptr_error(Out_Of_Memory);
            }
            op->yu[op->n_yu] = (unit_set*)stuff;
            ((unit_set*)stuff)->axis = IS_Y_UNIT_SET;
            op->n_yu++;
            op->need_to_refresh = 1;
        }
        else if (type == IS_T_UNIT_SET)
        {
            if (op->n_tu >= op->m_tu )
            {
                op->m_tu += MAX_DATA;
                op->tu = (unit_set**)realloc(op->tu,op->m_tu*sizeof(unit_set*));
                if (op->tu == NULL)		xvin_ptr_error(Out_Of_Memory);
            }
            op->tu[op->n_tu] = (unit_set*)stuff;
            ((unit_set*)stuff)->axis = IS_T_UNIT_SET;
            op->n_tu++;
            op->need_to_refresh = 1;
        }
        else 	i = 1;
        return i;
    }

    int add_one_plot_data (one_plot *op, int type, void *stuff)
    {
        return add_data_to_one_plot (op, type, stuff);
    }

    int init_data_set(one_plot *op)
    {
        data_set *ds;

        if (op == NULL)  return 1;
        if (op->n_dat > 0)
        {
            ds = op->dat[op->n_dat - 1];
            if (ds->nx == 0 || ds->ny == 0)       return 0;
        }
        ds = build_adjust_data_set(NULL, GR_SIZE, GR_SIZE);
        if (ds == NULL)       return 1;
        ds->nx = 0;
        ds->ny = 0;
        add_one_plot_data(op, IS_DATA_SET, (void *)ds);
        return 0;
    }

    int push_new_data(one_plot *op, float tx, float ty)
    {
        data_set *ds;

        if (op == NULL)  return 1;
        if (op->n_dat == 0)   if (init_data_set(op)) return 1;
        ds = op->dat[op->n_dat - 1];
        if ( ds->nx >= ds->mx || ds->ny >= ds->my)
        {
            ds = build_adjust_data_set(ds, ds->mx + GR_SIZE, ds->my + GR_SIZE);
            if (ds == NULL)       return 1;
        }
        ds->xd[ds->nx] = tx;
        ds->yd[ds->ny] = ty;
        ds->nx++;
        ds->ny++;
        return 0;
    }

    int close_data_set(one_plot *op)
    {
        data_set *ds, *dd;

        if (op == NULL)  return 1;
        if (op->n_dat == 0)           return 1;
        ds = op->dat[op->n_dat - 1];
        if (ds->nx == 0 || ds->ny == 0)       return 1;
        dd = duplicate_data_set(ds, NULL);
        if (dd == NULL)               return 1;
        dd->time = ds->time;
        op->dat[op->n_dat - 1] = dd;
        free_data_set(ds);
        return 0;
    }

    char *get_next_line(IFile & ifile, char *line)
    {
        char *c = NULL;
        int get_out = 0;
        
        do
        {
            get_out = 0;
            ifile.n_line++;
            c = fgets(line,B_LINE,ifile.fpi);
            if ( c == NULL)			get_out = 0;
            else if (strlen(c) == 1)	// added 2005-10-04, to compensate from MacOS behavior
                {	if (c[0]==10) 	get_out = 1;	// only if a blank line is encountered we continue
                    else			return(NULL);	// any other single character announces the binary region
                }
            else if (c[0]==26) return(NULL); // added 2006-03-04, for Linux
        } while(get_out);
        return(c); 
    }

    int get_label(IFile & ifile, char **c1, char **c2, char *line)
    {
        register int j = 0;
        int  k = 0, out_loop = 1;
        char  ch = '"', last_ch = 0;

        if (c1 == NULL || c2 == NULL || line == NULL)  return -2;

        (*c1)++;
        while ( out_loop ) /* looking for label end */
        {
            if((*c1)[j] == 0)	/* label extend to next line */
            {
                if (((*c1) = get_next_line(ifile, line)) == NULL )
                {
                    error_in_file("EOF reached before label ended");
                    k = -1;
                    out_loop = 0;
                    return k;
                }
                j=0;
            }
            if ( (*c1)[j] == 0) 				out_loop = 0;
            else if ( ((*c1)[j] == ch) && (last_ch != 92))	out_loop = 0;
            else
            {
                last_ch = (*c1)[j];
                (*c2)[k++] = (*c1)[j++];
            }
            if ( k >= B_LINE )
            {
                error_in_file("this label is too long !...\n%s",(*c2));
                k = -1;
                out_loop = 0;
                return k;
            }
        }
        (*c2)[k]=0;
        (*c1) = (*c1)+j+1;
        return (k);
    }

    int gr_numb(float *np, int *argcp, char ***argvp)
    {
        register int i;

        if (*argcp <= 1)		return(0);
        i = sscanf((*argvp)[1],"%f",np);
        (*argcp)--;
        (*argvp)++;
        return(i);
    }

    int gr_numbi(int *np, int *argcp, char ***argvp)
    {
        register int i;

        if (*argcp <= 1)		return(0);
        i = sscanf((*argvp)[1],"%d",np);
        (*argcp)--;
        (*argvp)++;
        return(i);
    }

    int push_bin_float_data_z(one_plot *op, char const *filename, int offset, int nx)
    {
        register int i, j;
        char ch;
        int ret = 0;
        size_t len;
        FILE *binfp;
        data_set *ds = NULL;
        static char previous_file[512];
        static int first = 1;
        static long int cz = 0;

        if (op == NULL)  return 1;
        binfp = fopen (filename, "rb");
        if ( binfp == NULL )
            error_in_file ("%s binary file not found!...  \n", (filename));

        if (first)
        {
            strncpy(previous_file, filename, sizeof(previous_file));
            first = 0;
        }
        len = strlen(filename);
        len = (len > strlen(previous_file)) ? strlen(previous_file) : len;
        if (cz == 0 || strncmp(previous_file, filename, len) != 0 )
        {
            strncpy(previous_file, filename, sizeof(previous_file));
            while (fread (&ch, sizeof (char), 1, binfp) == 1 && ch != CRT_Z);
            cz = ftell(binfp);
            fseek(binfp, offset, SEEK_CUR);
        }
        else fseek(binfp, cz + offset, SEEK_SET);

        if (op->n_dat == 0)   if (init_data_set(op)) return 1;
        ds = op->dat[op->n_dat - 1];
        if ( nx >= ds->mx || nx >= ds->my)
            ds = build_adjust_data_set(ds, nx, nx);
        if (ds == NULL)
        {
            fclose(binfp);
            error_in_file ("could not create data set in binary input file \n%s \n", (filename));
        }
        if ( absf == 0 )
        {
            if (fread (ds->xd, sizeof(float), nx, binfp) != (size_t) nx)
                error_in_file ("could not read x binary data in file \n%s \n", (filename));
            if (fread (ds->yd, sizeof(float), nx, binfp) != (size_t) nx)
                error_in_file ("could not read y binary data in file \n%s \n", (filename));

#ifdef XV_MAC
#ifdef MAC_POWERPC
            swap_bytes(ds->xd, nx, sizeof(float));
            swap_bytes(ds->yd, nx, sizeof(float));
#endif
#endif
            for (i = j = 0; i < nx; i++)
                j = (std::isnan(ds->yd[i]) || std::isnan(ds->xd[i])) ? j + 1 : j;

        }
        else if ( absf == 1 || absf == 2 )
        {
            if (fread (ds->yd, sizeof(float), nx, binfp) != (size_t) nx)
                error_in_file ("could not read y binary data in file \n%s \n", (filename));
#ifdef XV_MAC
#ifdef MAC_POWERPC
            swap_bytes(ds->xd, nx, sizeof(float));
#endif
#endif
            for (i = 0; i < nx; i++)
                ds->xd[i] = i * dx + abslow ;
            for (i = j = 0; i < nx; i++)
                j = (std::isnan(ds->yd[i]) || std::isnan(ds->xd[i])) ? j + 1 : j;
        }
        else ret = 1;
        ds->nx = nx;
        ds->ny = nx;
        fclose (binfp);
        return (ret) ? -1 : nx;
    }

    int push_bin_float_error_z(one_plot *op, const char *filename, int offset, int nx, int axis)
    {
        //register int i;
        char ch;
        int ret = 0;
        size_t len;
        float *array = NULL;
        FILE *binfp;
        data_set *ds = NULL;
        static char previous_file[512];
        static int first = 1;
        static long int cz = 0;

        if (op == NULL)  return 1;
        binfp = fopen (filename, "rb");
        if ( binfp == NULL )
            error_in_file ("binary file not found!...  \n", filename);
        if (first)
        {
            strncpy(previous_file, filename, sizeof(previous_file));
            first = 0;
        }
        len = strlen(filename);
        len = (len > strlen(previous_file)) ? strlen(previous_file) : len;
        if (cz == 0 || strncmp(previous_file, filename, len) != 0 )
        {
            strncpy(previous_file, filename, sizeof(previous_file));
            while (fread (&ch, sizeof (char), 1, binfp) == 1 && ch != CRT_Z);
            cz = ftell(binfp);
            fseek(binfp, offset, SEEK_CUR);
        }
        else fseek(binfp, cz + offset, SEEK_SET);
        if (op->n_dat == 0)   if (init_data_set(op)) return 1;
        ds = op->dat[op->n_dat - 1];

        if (axis == X_AXIS)
        {
            if (ds->xe != NULL) free(ds->xe);
            if ((alloc_data_set_x_error(ds) == NULL) || (ds->xe == NULL))
               error_in_file("I can't create errors !");
            array = ds->xe;
        }
        else if (axis == Y_AXIS)
        {
            if (ds->ye != NULL) free(ds->ye);
            if ((alloc_data_set_y_error(ds) == NULL) || (ds->ye == NULL))
                error_in_file("I can't create errors !");
            array = ds->ye;
        }

        if (array == NULL)
        {
            fclose(binfp);
            error_in_file ("could not create data set error in binary input file \n%s \n", (filename));
        }

        if (fread (array, sizeof(float), nx, binfp) != (size_t) nx)
            error_in_file ("could not read x binary data in file \n%s \n", (filename));
        else ret = 1;
        fclose (binfp);
        return (ret) ? -1 : nx;
    }

    int push_bin_float_data(one_plot *op, const char *filename)
    {
        register int i;
        int n_read, ntot = 0;
        float *tmp_y;
        FILE *binfp;

        if (op == NULL)  return 1;
        binfp = fopen (filename, "rb");
        if ( binfp == NULL )
            error_in_file ("%s file not found!...  \n", filename);
        tmp_y = (float *)calloc(GR_SIZE, sizeof(float));
        if (tmp_y == NULL)
        {
            fprintf(stderr, "calloc error \n");
            exit(1);
        }
        do
        {
            n_read = fread ( tmp_y , sizeof (float),  GR_SIZE, binfp);
#ifdef XV_MAC
#ifdef MAC_POWERPC
            swap_bytes(tmp_y, GR_SIZE, sizeof(float));
#endif
#endif
            if ( absf == 0 )
            {
                for ( i = 0; i < n_read ; i++, i++)
                {

                    push_new_data(op, tmp_y[i], tmp_y[i + 1]);
                }
            }
            else if ( absf == 1 || absf == 2 )
            {
                for ( i = 0; i < n_read ; i++)
                {


                    push_new_data(op, counter * dx + abslow, tmp_y[i]);
                    counter++;
                }
            }
            ntot += n_read;
        }
        while (n_read == GR_SIZE);
        if (tmp_y)   free(tmp_y);
        fclose (binfp);
        return ntot;
    }

    int push_bin_int_data(one_plot *op, const char *filename)
    {
        register int i;
        int n_read, ntot = 0;
        short int *tmp_y;
        FILE *binfp;

        if (op == NULL)  return 1;
        binfp = fopen (filename, "rb");
        if ( binfp == NULL )
            error_in_file ("%s file not found!...  \n", filename);
        tmp_y = (short int *)calloc(GR_SIZE, sizeof(int));
        if (tmp_y == NULL)
        {
            fprintf(stderr, "calloc error \n");
            exit(1);
        }
        do
        {
            n_read = fread ( tmp_y , sizeof (short int),  GR_SIZE, binfp);
#ifdef XV_MAC
#ifdef MAC_POWERPC
            swap_bytes(tmp_y, GR_SIZE, sizeof(short int));
#endif
#endif
            if ( absf == 0 )
            {
                for ( i = 0; i < n_read ; i++, i++)
                    push_new_data(op, (float)tmp_y[i], (float)tmp_y[i + 1]);
            }
            else if ( absf == 1 || absf == 2 )
            {
                for ( i = 0; i < n_read ; i++)
                {
                    push_new_data(op, counter * dx + abslow, (float)tmp_y[i]);
                    counter++;
                }
            }
            ntot += n_read;
        }
        while (n_read == GR_SIZE);
        if (tmp_y)  free(tmp_y);
        fclose (binfp);
        return ntot;
    }

    int push_plot_label(one_plot *op, float tx, float ty, char *label, int type)
    {
        plot_label *pl;

        if (op == NULL || label == NULL)  return 1;
        pl = (plot_label *)calloc(1, sizeof(struct plot_label));
        if ( pl == NULL )
        {
            fprintf (stderr, "realloc error \n");
            exit(1);
        }
        pl->xla = tx;
        pl->yla = ty;
        pl->text = (char *)strdup(label);
        pl->type = type;
        if (pl->text == NULL)
        {
            fprintf(stderr, "strdup error \n");
            exit(1);
        }
        return    add_one_plot_data (op, IS_PLOT_LABEL, (void *)pl);
    }

    int pltxlimread(one_plot *op, int *argcp, char ***argvp)
    {
        if (op == NULL || argcp == NULL)  return -1;
        if (!gr_numb(&(op->x_lo), argcp, argvp))     return 0;
        if (!gr_numb(&(op->x_hi), argcp, argvp))     return 1;
        op->iopt2 |= X_LIM;
        return 2;
    }
    int pltylimread(one_plot *op, int *argcp, char ***argvp)
    {
        if (op == NULL || argcp == NULL)  return -1;
        if (!gr_numb(&(op->y_lo), argcp, argvp))     return 0;
        if (!gr_numb(&(op->y_hi), argcp, argvp))     return 1;
        op->iopt2 |= Y_LIM;
        return 2;
    }
    int set_plot_opts(IFile & ifile, one_plot *op, int argc, char **argv, char *line, int check)
    {
        char file_name[66], *cmd, *tmpch;
        float templ, temp1;
        int itemp, decade = 0, type = 0, subtype = 0, offset = 0, n_item = 0;
        unit_set *un;


        file_name[0] = 0;
        while (--argc > 0)
        {
            argv++;
            cmd = argv[0];

            again:
            switch (argv[0][0])
            {
            case '-':       /* option delimeter */
                argv[0]++;
                goto again;
            case 'i':       /* input file */
                if ( argv[0][1] == 'b' && argv[0][2] == 'f' && argv[0][3] == 'z')
                {
                    if (!gr_numbi(&offset, &argc, &argv))   break;
                    if (!gr_numbi(&n_item, &argc, &argv))   break;

                    if (check == 0)
                        push_bin_float_data_z(op, ifile.filename, offset, n_item);
                }
                else if ( argv[0][1] == 'b' && argv[0][2] == 'f'  )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (plt_data_path[0] != 0)
                            snprintf(file_name, sizeof(file_name), "%s%s", plt_data_path, argv[0]);
                        else snprintf(file_name, sizeof(file_name), "%s", argv[0]);
                        if (check == 0)       push_bin_float_data(op, file_name);
                    }
                }
                else if ( argv[0][1] == 'b' && argv[0][2] == 'i' )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (plt_data_path[0] != 0)
                            snprintf(file_name, sizeof(file_name), "%s%s", plt_data_path, argv[0]);
                        else snprintf(file_name, sizeof(file_name), "%s", argv[0]);
                        if (check == 0)       push_bin_int_data(op, file_name);
                    }
                }
                /* send directly to the output */
                else if ( argv[0][1] == 'd' && argv[0][2] == 'u' )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        printf("%s\n", argv[0]);
                    }
                }
                else if (argc >= 2)
                {
                    argc--;
                    argv++;
                    if (plt_data_path[0] != 0)
                        snprintf(file_name, sizeof(file_name), "%s%s", plt_data_path, argv[0]);
                    else snprintf(file_name, sizeof(file_name), "%s", argv[0]);
                    ifile.n_line = 0;
                    ifile.filename = strdup(file_name);
                    ifile.fpi = fopen(ifile.filename, "r");
                    if ( ifile.fpi == NULL)
                    {
                        error_in_file("cannot open file\n %s", ifile.filename);
                        return MAX_ERROR;
                    }
                }
                break;


            case 'e':       /* input error from file */
                if ( argv[0][1] == 'x' && argv[0][2] == 'b' && argv[0][3] == 'f' && argv[0][4] == 'z')
                {
                    if (!gr_numbi(&offset, &argc, &argv))   break;
                    if (!gr_numbi(&n_item, &argc, &argv))   break;

                    if (check == 0)
                        push_bin_float_error_z(op, ifile.filename, offset, n_item, X_AXIS);
                }
                if ( argv[0][1] == 'y' && argv[0][2] == 'b' && argv[0][3] == 'f' && argv[0][4] == 'z')
                {
                    if (!gr_numbi(&offset, &argc, &argv))   break;
                    if (!gr_numbi(&n_item, &argc, &argv))   break;

                    if (check == 0)
                        push_bin_float_error_z(op, ifile.filename, offset, n_item, Y_AXIS);
                }


            case 'l':       /* label for plot */
                if ( strncmp(argv[0], "lxp", 3) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->x_prime_title = Mystrdupre(op->x_prime_title, argv[0]);
                    }
                }
                else if ( strncmp(argv[0], "lx", 2) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->x_title = Mystrdupre(op->x_title, argv[0]);
                    }
                }
                else if ( strncmp(argv[0], "lyp", 3) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->y_prime_title = Mystrdupre(op->y_prime_title, argv[0]);
                    }
                }
                else if ( strncmp(argv[0], "ly", 2) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->y_title = Mystrdupre(op->y_title, argv[0]);
                    }
                }
                else if ( strncmp(argv[0], "lr", 2) == 0 )
                {
                    if (argc >= 4)
                    {
                        if (!gr_numb(&templ, &argc, &argv))   break;
                        if (!gr_numb(&temp1, &argc, &argv)) break;
                        argc--;
                        argv++;
                        if (check == 0)
                        {
                            if (op->dat[op->n_dat - 1]->nx == 0)
                            {
                                push_plot_label_in_ds(op->dat[op->n_dat - 1], templ, temp1, argv[0], ABS_COORD);
                            }
                            else push_plot_label(op, templ, temp1, argv[0], ABS_COORD);
                        }
                    }
                }
                else if ( strncmp(argv[0], "layr", 4) == 0 )
                {
                    if (argc >= 4)
                    {
                        if (!gr_numb(&templ, &argc, &argv))   break;
                        if (!gr_numb(&temp1, &argc, &argv)) break;
                        argc--;
                        argv++;
                        if (check == 0)
                        {
                            if (op->dat[op->n_dat - 1]->nx == 0)
                            {
                                push_plot_label_in_ds(op->dat[op->n_dat - 1], templ, temp1, argv[0], VERT_LABEL_ABS);
                            }
                            else push_plot_label(op, templ, temp1, argv[0], VERT_LABEL_ABS);
                        }
                    }
                }
                else if ( strncmp(argv[0], "lay", 3) == 0 )
                {
                    if (argc >= 4)
                    {
                        if (!gr_numb(&templ, &argc, &argv))   break;
                        if (!gr_numb(&temp1, &argc, &argv)) break;
                        argc--;
                        argv++;
                        if (check == 0)
                        {
                            if (op->dat[op->n_dat - 1]->nx == 0)
                            {
                                push_plot_label_in_ds(op->dat[op->n_dat - 1], templ, temp1, argv[0], VERT_LABEL_USR);
                            }
                            else push_plot_label(op, templ, temp1, argv[0], VERT_LABEL_USR);
                        }
                    }
                }

                else
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->title = Mystrdupre(op->title, argv[0]);
                    }
                }
                break;
            case 'p':       /* prefix and unit */
                if ( argv[0][1] == 'x' )
                {
                    if (argc >= 3)
                    {
                        argc--;
                        argv++;
                        if ((argv[0][0] != '!' ) && (check == 0))
                            op->x_prefix = Mystrdupre(op->x_prefix, argv[0]);
                        argc--;
                        argv++;
                        if ((argv[0][0] != '!' ) && (check == 0))
                            op->x_unit = Mystrdupre(op->x_unit, argv[0]);
                    }
                    else
                    {
                        error_in_file("-p prefix unit:\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                }
                else if ( argv[0][1] == 'y' )
                {
                    if (argc >= 3)
                    {
                        argc--;
                        argv++;
                        if ((argv[0][0] != '!' ) && (check == 0))
                            op->y_prefix = Mystrdupre(op->y_prefix, argv[0]);
                        argc--;
                        argv++;
                        if ((argv[0][0] != '!' ) && (check == 0))
                            op->y_unit = Mystrdupre(op->y_unit, argv[0]);
                    }
                    else
                    {
                        error_in_file("-p prefix unit:\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                }
                else if ( argv[0][1] == 't' )
                {
                    if (argc >= 3)
                    {
                        argc--;
                        argv++;
                        if ((argv[0][0] != '!' ) && (check == 0))
                            op->t_prefix = Mystrdupre(op->t_prefix, argv[0]);
                        argc--;
                        argv++;
                        if ((argv[0][0] != '!' ) && (check == 0))
                            op->t_unit = Mystrdupre(op->t_unit, argv[0]);
                    }
                    else
                    {

                        error_in_file("-p prefix unit:\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                }
                break;
            case 'd':       /* output device */
                if ( argv[0][1] == 'p' )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if ( strncpy(plt_data_path, argv[0], sizeof(plt_data_path)) == NULL)
                            fprintf (stderr, "not valid data path %s   \n", argv[0]);
                    }
                    else
                    {
                        error_in_file("-dp plt_data_path:\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                }
                break;
            case 'm':       /* line mode */
                if ((check == 0) && (op->n_dat != 0))
                {
                    close_data_set(op);
                    init_data_set(op);
                }
                if (!gr_numb(&templ, &argc, &argv))
                    itemp = argv[0][1] - '0';
                else
                    itemp = (int)templ;
                switch (itemp)
                {
                case -'0':  /* null character */
                case 0:
                    if (check == 0) op->dat[op->n_dat - 1]->m = 0;
                    break;
                case 2:
                    if (check == 0) op->dat[op->n_dat - 1]->m = 2;
                    break;
                }
                break;
            case 'a':       /* automatic abscissas */
                if ( strncmp(argv[0], "axp", 3) == 0 )
                {
                    if (!gr_numbi(&itemp, &argc, &argv))    break;
                    if (check == 0) op->c_xu_p = itemp;
                }
                else if ( strncmp(argv[0], "ayp", 3) == 0 )
                {
                    if (!gr_numbi(&itemp, &argc, &argv))    break;
                    if (check == 0) op->c_yu_p = itemp;
                }
                else if ( argv[0][1] == '!')          absf = 0;
                else if ( strncmp(argv[0], "ax", 2) == 0 )
                {
                    if (check == 0) op->dx = 1;
                    if (!gr_numb(&templ, &argc, &argv))  break;
                    if (check == 0) op->dx = templ;
                    if (!gr_numb(&templ, &argc, &argv))  break;
                    if (check == 0) op->ax = templ;
                }
                else if ( strncmp(argv[0], "ay", 2) == 0 )
                {
                    if (check == 0) op->dy = 1;
                    if (!gr_numb(&templ, &argc, &argv))  break;
                    if (check == 0) op->dy = templ;
                    if (!gr_numb(&templ, &argc, &argv))  break;
                    if (check == 0) op->ay = templ;
                }
                else
                {
                    absf = 1;
                    counter = 0;
                    abslow = 0;
                    dx = 1;
                    if (!gr_numb(&dx, &argc, &argv))
                        break;
                    if (gr_numb(&abslow, &argc, &argv))
                        absf = 2;
                }
                break;
            case 'g':       /* grid style */
                if (!gr_numb(&templ, &argc, &argv))
                    itemp = argv[0][1] - '0';
                else
                    itemp = (int)templ;
                switch (itemp)
                {
                case -'0':  /* null character */
                case 0:
                    if (check == 0)   op->iopt |= NOAXES;/*iopt+=NOAXES;*/
                    break;
                case 1:
                    if (check == 0)   op->iopt |= TRIM;/*iopt += TRIM;*/
                    break;
                case 3:
                    if (check == 0)   op->iopt |= AXES_PRIME;
                    break;
                }
                break;
            case 'c':       /* plotting characters */
                if ( strncmp(argv[0], "color", 5) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                        {
                            if (strncmp(argv[0], "black", 5) == 0)
                                op->dat[op->n_dat - 1]->color =  Black;
                            else if (strncmp(argv[0], "blue", 4) == 0)
                                op->dat[op->n_dat - 1]->color =  Blue;
                            else if (strncmp(argv[0], "green", 5) == 0)
                                op->dat[op->n_dat - 1]->color =  Green;
                            else if (strncmp(argv[0], "cyan", 4) == 0)
                                op->dat[op->n_dat - 1]->color =  Cyan;
                            else if (strncmp(argv[0], "red", 3) == 0)
                                op->dat[op->n_dat - 1]->color =  Red;
                            else if (strncmp(argv[0], "magenta", 7) == 0)
                                op->dat[op->n_dat - 1]->color =  Magenta;
                            else if (strncmp(argv[0], "brown", 5) == 0)
                                op->dat[op->n_dat - 1]->color =  Brown;
                            else if (strncmp(argv[0], "lightgray", 9) == 0)
                                op->dat[op->n_dat - 1]->color =  Lightgray;
                            else if (strncmp(argv[0], "darkgray", 8) == 0)
                                op->dat[op->n_dat - 1]->color =  Darkgray;
                            else if (strncmp(argv[0], "lightblue", 9) == 0)
                                op->dat[op->n_dat - 1]->color =  Lightblue;
                            else if (strncmp(argv[0], "lightgreen", 10) == 0)
                                op->dat[op->n_dat - 1]->color =  Lightgreen;
                            else if (strncmp(argv[0], "lightcyan", 9) == 0)
                                op->dat[op->n_dat - 1]->color =  Lightcyan;
                            else if (strncmp(argv[0], "lightred", 8) == 0)
                                op->dat[op->n_dat - 1]->color =  Lightred;
                            else if (strncmp(argv[0], "lightmagenta", 12) == 0)
                                op->dat[op->n_dat - 1]->color =  Lightmagenta;
                            else if (strncmp(argv[0], "yellow", 6) == 0)
                                op->dat[op->n_dat - 1]->color =  Yellow;
                            else if (strncmp(argv[0], "white", 5) == 0)
                                op->dat[op->n_dat - 1]->color =  White;
                        }
                    }
                }
                else
                {
                    if ((check == 0) && (op->n_dat != 0))
                    {
                        close_data_set(op);
                        init_data_set(op);
                    }
                    if (argc >= 2)
                    {
                        if (check == 0)
                            op->dat[op->n_dat - 1]->symb = Mystrdupre(op->dat[op->n_dat - 1]->symb, argv[1]);
                        argv++;
                        argc--;
                    }
                }
                break;
            case 's':
                if ( strncmp(argv[0], "src", 3) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->dat[op->n_dat - 1]->source = Mystrdupre(op->dat[op->n_dat - 1]->source, argv[0]);
                    }
                }
                if ( strncmp(argv[0], "special", 7) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            add_one_plot_data(op, IS_SPECIAL, (void *)argv[0]);
                    }
                }
                break;

            case 't':       /* transpose x and y */
                if ( strncmp(argv[0], "tus", 3) == 0 )
                {
                    if (argc < 4)
                    {
                        error_in_file("-tus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    itemp = 0;
                    templ = 1;
                    temp1 = 0;
                    if (!gr_numb(&templ, &argc, &argv))      itemp = 1;
                    if (!gr_numb(&temp1, &argc, &argv))     itemp = 1;
                    if (itemp)
                    {
                        error_in_file("-xus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    argc--;
                    argv++;
                    tmpch = strdup(argv[0]);
                    type = 0;
                    decade = 0;
                    subtype = 0;
                    if (argc >= 3)
                    {
                        if (!gr_numbi(&type, &argc, &argv))     itemp = 1;
                        if (!gr_numbi(&decade, &argc, &argv))   itemp = 1;
                        if (!gr_numbi(&subtype, &argc, &argv))  itemp = 2;
                        if (itemp == 1)
                        {
                            error_in_file("-xus :\nInvalid argument\n"
                                                 "%s\nline %s", cmd, line);
                        }
                    }
                    else if (unit_to_type(tmpch, &type, &decade))
                    {
                        error_in_file("-xus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    un = build_unit_set(type, temp1, templ, (char)decade, 0, tmpch);
                    if (tmpch)
                    {
                        free(tmpch);
                        tmpch = NULL;
                    }
                    if (un == NULL)
                    {
                        error_in_file("-tus :\ncan't create\n%s\nline %s"
                                             , cmd, line);
                    }
                    un->sub_type = subtype;
                    if (check == 0)
                        add_one_plot_data (op, IS_T_UNIT_SET, (void *)un);

                }
                else if ( argv[0][1] == 'k' && argv[0][2] == 'x')
                {
                    gr_numb(&templ, &argc, &argv);
                    if (check == 0) op->tick_len_x = templ;
                }
                else if ( argv[0][1] == 'k' && argv[0][2] == 'y')
                {
                    gr_numb(&templ, &argc, &argv);
                    if (check == 0) op->tick_len_y = templ;
                }
                else if ( argv[0][1] == 'k')
                {
                    gr_numb(&templ, &argc, &argv);
                    if (check == 0) op->tick_len = templ;
                }
                else  if ( strncmp(argv[0], "treat", 5) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->dat[op->n_dat - 1]->treatement = Mystrdupre(op->dat[op->n_dat - 1]->treatement, argv[0]);
                    }
                }
                else  if ( strncmp(argv[0], "time", 5) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                        {
                            if (sscanf(argv[0], "%lu", &(op->dat[op->n_dat - 1]->time)) != 1)
                            {
                                error_in_file("Improper time\n\\it %s %s\n%s",
                                                     cmd, argv[0], line);
                            }
                        }
                    }
                }
                else
                {
                    if (check == 0) op->iopt |= CROSS;
                }
                break;
            case 'x':       /* x limits */
                if ( strncmp(argv[0], "xus", 3) == 0 )
                {
                    if (argc < 4)
                    {
                        error_in_file("-xus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    itemp = 0;
                    templ = 1;
                    temp1 = 0;
                    if (!gr_numb(&templ, &argc, &argv))      itemp = 1;
                    if (!gr_numb(&temp1, &argc, &argv))     itemp = 1;
                    if (itemp)
                    {
                        error_in_file("-xus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    argc--;
                    argv++;
                    tmpch = strdup(argv[0]);
                    type = 0;
                    decade = 0;
                    subtype = 0;
                    if (argc >= 3)
                    {
                        if (!gr_numbi(&type, &argc, &argv))     itemp = 1;
                        if (!gr_numbi(&decade, &argc, &argv))   itemp = 1;
                        if (!gr_numbi(&subtype, &argc, &argv))  itemp = 2;
                        if (itemp == 1)
                        {
                            error_in_file("-xus :\nInvalid argument\n"
                                                 "%s\nline %s", cmd, line);
                        }
                    }
                    else if (unit_to_type(tmpch, &type, &decade))
                    {
                        error_in_file("-xus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    un = build_unit_set(type, temp1, templ, (char)decade, 0, tmpch);
                    if (tmpch)
                    {
                        free(tmpch);
                        tmpch = NULL;
                    }
                    if (un == NULL)
                    {
                        error_in_file("-xus :\ncan't create\n%s\nline %s"
                                             , cmd, line);
                    }
                    un->sub_type = subtype;
                    if (check == 0)
                        add_one_plot_data (op, IS_X_UNIT_SET, (void *)un);

                }
                else
                {
                    if (check == 0)
                    {
                        if ( argv[0][1] == 'n') op->iopt2 &= ~X_NUM;
                        else          op->iopt2 |= X_NUM;
                    }
                    if (argc > 1 && argv[1][0] == 'l')
                    {
                        argc--;
                        argv++;
                        if (check == 0) op->iopt |= XLOG;
                    }
                    if (check == 0)       pltxlimread(op, &argc, &argv);
                    else
                    {
                        gr_numb(&templ, &argc, &argv);
                        gr_numb(&templ, &argc, &argv);
                    }
                }
                break;
            case 'y':       /* y limits */
                if ( strncmp(argv[0], "yus", 3) == 0 )
                {
                    if (argc < 4)
                    {
                        error_in_file("-yus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    itemp = 0;
                    templ = 1;
                    temp1 = 0;
                    if (!gr_numb(&templ, &argc, &argv))      itemp = 1;
                    if (!gr_numb(&temp1, &argc, &argv))     itemp = 1;
                    if (itemp)
                    {
                        error_in_file("-yus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    argc--;
                    argv++;
                    tmpch = strdup(argv[0]);
                    type = 0;
                    decade = 0;
                    subtype = 0;
                    if (argc >= 3)
                    {
                        if (!gr_numbi(&type, &argc, &argv))     itemp = 1;
                        if (!gr_numbi(&decade, &argc, &argv))   itemp = 1;
                        if (!gr_numbi(&subtype, &argc, &argv))  itemp = 2;
                        if (itemp == 1)
                        {
                            error_in_file("-yus :\nInvalid argument\n"
                                                 "%s\nline %s", cmd, line);
                        }
                    }
                    else if (unit_to_type(tmpch, &type, &decade))
                    {
                        error_in_file("-yus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    un = build_unit_set(type, temp1, templ, (char)decade, 0, tmpch);
                    if (un == NULL)
                    {
                        error_in_file("-yus :\ncant create\n"
                                             "%s\nline %s", cmd, line);
                    }
                    if (tmpch)
                    {
                        free(tmpch);
                        tmpch = NULL;
                    }
                    un->sub_type = subtype;
                    if (check == 0)
                        add_one_plot_data (op, IS_Y_UNIT_SET, (void *)un);
                }
                else
                {
                    if (check == 0)
                    {
                        if ( argv[0][1] == 'n')       op->iopt2 &= ~Y_NUM;
                        else                      op->iopt2 |= Y_NUM;
                    }
                    if (argc > 1 && argv[1][0] == 'l')
                    {
                        argc--;
                        argv++;
                        if (check == 0) op->iopt |= YLOG;
                    }
                    if (check == 0)   pltylimread(op, &argc, &argv);
                    else
                    {
                        gr_numb(&templ, &argc, &argv);
                        gr_numb(&templ, &argc, &argv);
                    }
                }
                break;
            case 'h':
                if (strncmp(argv[0], "his", 3) == 0)
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->dat[op->n_dat - 1]->history = Mystrdupre(op->dat[op->n_dat - 1]->history, argv[0]);
                    }
                }
                else if (gr_numb(&templ, &argc, &argv))
                {
                    if (check == 0) op->height = templ;
                    sizef++;
                }
                break;
            case 'w':
                if (gr_numb(&templ, &argc, &argv))
                {
                    if (check == 0)   op->width = templ;
                    sizef++;
                }
                break;
            case 'r':
                if (gr_numb(&templ, &argc, &argv))
                {
                    if (check == 0)   op->right = templ;
                    sizef++;
                }
                break;
            case 'u':
                if (gr_numb(&templ, &argc, &argv))
                {
                    if (check == 0)   op->up = templ;
                    sizef++;
                }
                break;
            default:
                if (check == 0)
                {
                    error_in_file("Plot Invalid argument\n"
                                         "%s\nline %s", cmd, line);
                }
                else
                {
                    return ++n_error;
                }
            }
        }
        return 0;
    }

    int init_one_plot(one_plot *op)
    {
        int i;
        unit_set	*un;

        if (op == NULL) return 1;
        op->width = op->height = 1;
        op->right = op->up = 0;
        op->iopt = 0;
        op->iopt2 = X_NUM + Y_NUM;
        op->tick_len = op->tick_len_x = op->tick_len_y = 1;
        op->x_lo = op->x_hi = op->y_lo = op->y_hi = 0;
        op->n_dat = op->cur_dat = op->n_lab = 0;
        op->dx = op->dy = op->dt = 1;
        op->dat = (data_set **)calloc(MAX_DATA,sizeof(data_set*));
        op->lab = (plot_label **)calloc(MAX_DATA,sizeof(plot_label*));
        if (op->dat == NULL || op->lab == NULL) xvin_ptr_error(Out_Of_Memory);
        op->m_lab = op->m_dat = MAX_DATA;
        op->n_xu = op->m_xu = op->c_xu = 0;
        op->n_yu = op->m_yu = op->c_yu = 0;
        op->n_tu = op->m_tu = op->c_tu = 0;
        op->c_xu_p = op->c_yu_p = op->c_tu_p = -1;
        op->filename = NULL;	op->dir = NULL;
        op->title = NULL;	op->x_title = NULL;	op->y_title = NULL;
        op->x_prime_title = op->y_prime_title = NULL;
        op->y_prefix = NULL;	op->x_prefix = NULL;   op->t_prefix = NULL;
        op->x_unit = NULL;	op->y_unit = NULL;     op->t_unit = NULL;
        op->xu = NULL;	op->yu = NULL;  op->tu = NULL;
        un = build_unit_set(IS_RAW_U, 0, 1, 0, 0, NULL);
        if (un == NULL)		xvin_ptr_error(Out_Of_Memory);
        add_one_plot_data (op, IS_X_UNIT_SET, (void *)un);
        un = build_unit_set(IS_RAW_U, 0, 1, 0, 0, NULL);
        if (un == NULL)		xvin_ptr_error(Out_Of_Memory);
        add_one_plot_data (op, IS_Y_UNIT_SET, (void *)un);
        un = build_unit_set(IS_RAW_U, 0, 1, 0, 0, NULL);
        if (un == NULL)		xvin_ptr_error(Out_Of_Memory);
        add_one_plot_data (op, IS_T_UNIT_SET, (void *)un);
        op->need_to_refresh = 1;
            op->data_changing = 0;
            op->transfering_data_to_box = 0;
        op->user_id = 0;
        op->read_only = false;
        for (i = 0; i < 16; i++)
          {
            op->user_ispare[i] = 0;
            op->user_fspare[i] = 0;
          }
        return 0;
    }
    int free_one_plot(one_plot *op)
    {
        int i;

        if (op == NULL) 	xvin_ptr_error(Wrong_Argument);
        for (i=0 ; i< op->n_dat ; i++)	free_data_set(op->dat[i]);
        if (op->dat)  {free(op->dat);  op->dat = NULL;}
        for (i=0 ; i< op->n_lab ; i++)
        {
            if (op->lab[i]->text != NULL) 	free(op->lab[i]->text);
            if (op->lab[i] != NULL) 	free(op->lab[i]);
        }
        if (op->lab)	{free(op->lab);	   op->lab = NULL;}
        if (op->filename != NULL)	free(op->filename);
        if (op->dir != NULL)		free(op->dir);
        if (op->title != NULL)		free(op->title);
        if (op->x_title != NULL)	free(op->x_title);
        if (op->y_title != NULL)	free(op->y_title);
        if (op->x_prime_title != NULL)	free(op->x_prime_title);
        if (op->y_prime_title != NULL)	free(op->y_prime_title);
        if (op->y_prefix != NULL)	free(op->y_prefix);
        if (op->x_prefix != NULL)	free(op->x_prefix);
        if (op->t_prefix != NULL)	free(op->t_prefix);
        if (op->x_unit != NULL)		free(op->x_unit);
        if (op->y_unit != NULL)		free(op->y_unit);
        if (op->t_unit != NULL)		free(op->t_unit);
        if (op->xu != NULL)
        {
            for (i=0 ; i< op->n_xu ; i++)	free_unit_set(op->xu[i]);
            free(op->xu);
        }
        if (op->yu != NULL)
        {
            for (i=0 ; i< op->n_yu ; i++)	free_unit_set(op->yu[i]);
            free(op->yu);
        }
        if (op->tu != NULL)
        {
            for (i=0 ; i< op->n_tu ; i++)	free_unit_set(op->tu[i]);
            free(op->tu);
        }
        free(op);	op = NULL;
        return 0;
    }
    int pltreadfile(one_plot *op, char const  *file_name, int check)
    {
        register int i, j, k;
        int load_abort = 0, total_line_read = 0;
        float tmpx, tmpy;
        char *c1, *c2;
        char *line, *line1;
        char **agv, **agvk;
        int agc = 0;

        //setlocale(LC_ALL, "C");

        if (op == NULL)    return MAX_ERROR;
        absf = n_error =  0;
        counter = 0;
        abslow = 0;
        dx = 1;
        if (aflag)
        {
            absf = 1;
            counter = 0;
            abslow = 0;
            dx = 1;
        }


        IFile ifile;
        ifile.n_line = 0;
        ifile.filename = file_name;
        ifile.fpi = fopen(file_name, "r");
        if ( ifile.fpi == NULL)
        {
            error_in_file("cannot open file\n");
            return MAX_ERROR;
        }

        line = (char *)calloc(B_LINE, sizeof(char));
        line1 = (char *)calloc(B_LINE, sizeof(char));
        agv = (char **)calloc(OP_SIZE, sizeof(char *));
        agvk = (char **)calloc(OP_SIZE, sizeof(char *));

        if ( line == NULL || line1 == NULL || agv == NULL || agvk == NULL)
        {
            error_in_file("malloc error \n");
            return MAX_ERROR;
        }

        while (load_abort < MAX_ERROR && total_line_read <= check)
        {
            while ((c1 = get_next_line(ifile, line)) == NULL)
            {
                if (ifile.fpi != NULL)
                    fclose(ifile.fpi);
            }

            if (check)    total_line_read++;
            if ( c1 == NULL)  break;
            line1[0] = 0;
            i = sscanf(line, "%f", &tmpx);
            if (i == 1)   i = sscanf(line, "%f%f", &tmpx, &tmpy);
            if (i == 2)   i = sscanf(line, "%f%f%s", &tmpx, &tmpy, line1);
            if (i == 3) /* may be a label */
            {
                if ( line1[0] == '%') /* start a comment */
                {
                    i = 2;
                    j = 0;
                }
                else if ( line1[0] == '"')/*start as a label*/
                {
                    c1 = strchr(line, '"');
                    c2 = line1;
                    j = get_label(ifile, &c1, &c2, line);
                }
                else
                {
                    error_in_file("a label must start and end\nwith a double quote !...\n->%s", line);
                }
                if (j != 0)
                {
                    if (check == 0)
                    {
                        if (op->n_dat > 0 && op->dat[op->n_dat - 1]->nx == 0)
                        {
                            push_plot_label_in_ds(op->dat[op->n_dat - 1], tmpx, tmpy, c2, USR_COORD);
                        }
                        else push_plot_label(op, tmpx, tmpy, c2, USR_COORD);
                    }
                }
                else if ( i == 3 )
                {
                    error_in_file ("empty label !...\n->%s", line);
                }
            }
            if ( i == 2)  /* may be a data point given by x,y */
            {
                if ( absf == 0)
                {
                    if (check == 0) push_new_data(op, tmpx, tmpy);
                }
                else
                {
                    error_in_file ("you can't input an x,y data point\n when you have specified a -a option\n->%s", line);
                }
            }
            if ( i == 1)  /* may be a data point given by y only */
            {
                if ( absf == 1 || absf == 2 )
                {
                    tmpy = counter * dx + abslow;
                    counter++;
                    if (check == 0) push_new_data(op, tmpy, tmpx);
                }
                else
                {
                    error_in_file ("you can't input data point with only y\nwithout specifying the -a option\n->%s", line);
                }
            }
            if ( i == 0 ) /* a command line */
            {
                /* advance to 1st item */
                while (*c1 == ' ' || *c1 == '\t' || *c1 == '#') c1++;
                for (k = 0 ; k < agc ; k++)
                {
                    if (agvk[k] != NULL)      free(agvk[k]);
                    agvk[k] = NULL;
                }
                agc = 1;

                while ( (c1 != NULL) && (*c1 != 0) )
                {
                    if ( *c1 == '%')  *c1 = 0;
                    else if ( *c1 != '"')
                    {
                        if (sscanf(c1, "%s", line1) == 1)
                        {
                            agvk[agc] = agv[agc] = strdup(line1);
                            agc++;
                        }
                        if (agc >= OP_SIZE)
                        {
                            error_in_file ("too many options\nin input line\n->%s", line);
                            load_abort = MAX_ERROR;
                        }
                        if (c1 != NULL && strchr(c1, ' ') != NULL)  c1 = strchr ( c1, ' ');
                        else if (c1 != NULL && strchr(c1, '\t') != NULL) c1 = strchr (c1, '\t');
                        else  *c1 = 0;
                    }
                    else
                    {
                        c2 = line1;
                        c2[0] = 0;
                        if (get_label(ifile, &c1, &c2, line))
                        {
                            agvk[agc] = agv[agc] = strdup(c2);
                            agc++;
                        }
                        if (agc >= OP_SIZE)
                        {
                            error_in_file("too many options\nin input line\n->%s", line);
                            load_abort = MAX_ERROR;
                        }
                    }
                    while (*c1 == ' ' || *c1 == '\t' || *c1 == '\n')
                    {
                        c1++;
                    }
                }
                if (agc > 1)
                {
                    if (set_plot_opts(ifile, op, agc, agv, line, check) == MAX_ERROR)
                        load_abort = MAX_ERROR;
                }
                for (k = 0 ; k < agc ; k++)
                {
                    if (agvk[k] != NULL)      free(agvk[k]);
                    agvk[k] = NULL;
                }
                agc = 1;
            }
        }
        if (line) free(line);
        if (line1) free(line1);
        if (agv) free(agv);
        if (agvk) free(agvk);
        if (check == 0)
        {
            for (i = 0, j = 1, op->c_xu = 0; i < op->n_xu && j != 0 ; i++)
            {
                j = 0;
                if (op->ax != op->xu[i]->ax)  j = 1;
                if (op->dx != op->xu[i]->dx)  j = 1;
                if (op->x_unit == NULL || op->xu[i]->name == NULL)    j = 1;
                else if (strncmp(op->xu[i]->name, op->x_unit, strlen(op->x_unit)) != 0) j = 1;
                if (j == 0)   op->c_xu = i;
            }
            for (i = 0, j = 1, op->c_yu = 0; i < op->n_yu && j != 0 ; i++)
            {
                j = 0;
                if (op->ay != op->yu[i]->ax)  j = 1;
                if (op->dy != op->yu[i]->dx)  j = 1;
                if (op->y_unit == NULL || op->yu[i]->name == NULL)    j = 1;
                else if (strncmp(op->yu[i]->name, op->y_unit, strlen(op->y_unit)) != 0) j = 1;
                if (j == 0)   op->c_yu = i;
            }
            for (i = 0, j = 1, op->c_tu = 0; i < op->n_tu && j != 0 ; i++)
            {
                j = 0;
                if (op->at != op->tu[i]->ax)  j = 1;
                if (op->dt != op->tu[i]->dx)  j = 1;
                if (op->t_unit == NULL || op->tu[i]->name == NULL)    j = 1;
                else if (strncmp(op->tu[i]->name, op->t_unit, strlen(op->t_unit)) != 0) j = 1;
                if (j == 0)   op->c_tu = i;
            }
        }
        return n_error;
    }
}}

namespace legacy
{
    GrData readgr(std::string fname)
    {
        one_plot * op = (one_plot *)calloc(1, sizeof(one_plot));
        init_one_plot(op);
        pltreadfile(op, fname.c_str(), 0);

        GrData result;
        if(op->title != nullptr)
            result.title = op->title;
        for (int i = 0; i< op->n_dat ; i++)
        {
            DsData ds;
            ds.xd.resize(op->dat[i]->nx);
            for(int k = 0; k < op->dat[i]->nx; ++k)
                ds.xd[k] = op->dat[i]->xd[i];
            ds.yd.resize(op->dat[i]->ny);
            for(int k = 0; k < op->dat[i]->ny; ++k)
                ds.yd[k] = op->dat[i]->yd[i];
            if(op->title != nullptr)
                ds.title = op->dat[i]->source;
            result.items.emplace_back(ds);
        }
        free_one_plot(op);
        return result;
    }
}
